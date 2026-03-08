"""Job document tools — save and retrieve per-job cover letters and resumes."""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from ._registry import agent_tool

logger = logging.getLogger(__name__)

VALID_DOC_TYPES = {"cover_letter", "resume"}


class SaveJobDocumentInput(BaseModel):
    job_id: int = Field(description="ID of the job to save the document for")
    doc_type: str = Field(description="Document type: 'cover_letter' or 'resume'")
    content: str = Field(description="The full document content")
    edit_summary: Optional[str] = Field(
        default=None,
        description="Brief description of what changed in this version",
    )


class GetJobDocumentInput(BaseModel):
    job_id: int = Field(description="ID of the job to get the document for")
    doc_type: str = Field(
        default="cover_letter",
        description="Document type: 'cover_letter' or 'resume'",
    )


class JobDocumentsMixin:
    @agent_tool(
        description=(
            "Save a cover letter or tailored resume for a job application. "
            "Creates a new version — previous versions are preserved as history."
        ),
        args_schema=SaveJobDocumentInput,
    )
    def save_job_document(self, job_id, doc_type, content, edit_summary=None):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.job_document import JobDocument

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}
        if doc_type not in VALID_DOC_TYPES:
            return {
                "error": (
                    f"Invalid doc_type '{doc_type}'. "
                    f"Must be one of: {', '.join(sorted(VALID_DOC_TYPES))}"
                )
            }

        doc = JobDocument(
            job_id=job_id,
            doc_type=doc_type,
            content=content,
            version=JobDocument.next_version(job_id, doc_type),
            edit_summary=edit_summary,
        )
        db.session.add(doc)
        db.session.commit()

        logger.info(
            "save_job_document: job_id=%d doc_type=%s version=%d",
            job_id, doc_type, doc.version,
        )
        return {
            "document": doc.to_dict(),
            "job": {"id": job.id, "company": job.company, "title": job.title},
        }

    @agent_tool(
        description="Get the latest cover letter or tailored resume saved for a job application.",
        args_schema=GetJobDocumentInput,
    )
    def get_job_document(self, job_id, doc_type="cover_letter"):
        from backend.database import db
        from backend.models.job import Job
        from backend.models.job_document import JobDocument

        job = db.session.get(Job, job_id)
        if not job:
            return {"error": f"Job with id {job_id} not found"}
        if doc_type not in VALID_DOC_TYPES:
            return {
                "error": (
                    f"Invalid doc_type '{doc_type}'. "
                    f"Must be one of: {', '.join(sorted(VALID_DOC_TYPES))}"
                )
            }

        doc = JobDocument.get_latest(job_id, doc_type)
        if not doc:
            return {"error": f"No {doc_type} found for job {job_id}"}

        return {
            "document": doc.to_dict(),
            "job": {"id": job.id, "company": job.company, "title": job.title},
        }
