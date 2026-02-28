"""Search result tools — add_search_result and list_search_results."""

import logging
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, Field

from ._registry import agent_tool

logger = logging.getLogger(__name__)

VALID_REMOTE_TYPES = {"onsite", "hybrid", "remote"}


def _coerce_int(v):
    """Coerce float-like values to int (e.g. 4.0 → 4, 4.5 → 4).

    Smaller models (Ollama) sometimes send floats for int fields.
    """
    if v is None:
        return v
    if isinstance(v, float):
        return int(v)
    return v


CoercedInt = Annotated[int, BeforeValidator(_coerce_int)]
CoercedOptionalInt = Annotated[Optional[int], BeforeValidator(_coerce_int)]


class AddSearchResultInput(BaseModel):
    company: str = Field(description="Company name")
    title: str = Field(description="Job title")
    job_fit: CoercedInt = Field(description="Job fit rating 0-5 based on user profile match")
    url: Optional[str] = Field(default=None, description="Job posting URL")
    salary_min: CoercedOptionalInt = Field(default=None, description="Minimum salary")
    salary_max: CoercedOptionalInt = Field(default=None, description="Maximum salary")
    location: Optional[str] = Field(default=None, description="Job location")
    remote_type: Optional[str] = Field(default=None, description="Remote type: remote, hybrid, or onsite")
    source: Optional[str] = Field(default=None, description="Where the job was found (jsearch, adzuna, web)")
    description: Optional[str] = Field(default=None, description="Brief job description summary")
    requirements: Optional[str] = Field(default=None, description="Key requirements, newline-separated")
    nice_to_haves: Optional[str] = Field(default=None, description="Nice-to-have qualifications, newline-separated")
    fit_reason: Optional[str] = Field(default=None, description="Brief explanation of the fit rating")


class ListSearchResultsInput(BaseModel):
    min_fit: CoercedOptionalInt = Field(default=None, description="Minimum fit rating 0-5")


class SearchResultsMixin:
    @agent_tool(
        description=(
            "Add a qualifying job to the search results panel. Only add jobs "
            "rated >=3/5 stars. Include structured data and a fit_reason."
        ),
        args_schema=AddSearchResultInput,
    )
    def add_search_result(self, company, title, job_fit, url=None,
                          salary_min=None, salary_max=None, location=None,
                          remote_type=None, source=None, description=None,
                          requirements=None, nice_to_haves=None,
                          fit_reason=None):
        from backend.database import db
        from backend.models.search_result import SearchResult

        if not self.conversation_id:
            return {"error": "No conversation context — cannot store search result"}

        if not (0 <= job_fit <= 5):
            return {"error": "job_fit must be between 0 and 5"}

        if remote_type and remote_type not in VALID_REMOTE_TYPES:
            return {"error": f"Invalid remote_type '{remote_type}'. Must be one of: {', '.join(sorted(VALID_REMOTE_TYPES))}"}

        result = SearchResult(
            conversation_id=self.conversation_id,
            company=company,
            title=title,
            url=url,
            salary_min=salary_min,
            salary_max=salary_max,
            location=location,
            remote_type=remote_type,
            source=source,
            description=description,
            requirements=requirements,
            nice_to_haves=nice_to_haves,
            job_fit=job_fit,
            fit_reason=fit_reason,
        )
        db.session.add(result)
        db.session.commit()

        result_dict = result.to_dict()
        logger.info(
            "add_search_result: id=%d company=%s title=%s fit=%d",
            result.id, company, title, job_fit,
        )

        # Emit SSE event so the frontend search results panel updates in real time
        if self.event_callback:
            self.event_callback({
                "event": "search_result_added",
                "data": result_dict,
            })

        return {"search_result": result_dict}

    @agent_tool(
        description="List job search results from the current conversation.",
        args_schema=ListSearchResultsInput,
    )
    def list_search_results(self, min_fit=None):
        from backend.models.search_result import SearchResult

        if not self.conversation_id:
            return {"error": "No conversation context — cannot query search results"}

        query = SearchResult.query.filter_by(conversation_id=self.conversation_id)

        if min_fit is not None:
            if not (0 <= min_fit <= 5):
                return {"error": "min_fit must be between 0 and 5"}
            query = query.filter(SearchResult.job_fit >= min_fit)

        results = query.order_by(SearchResult.created_at.desc()).all()

        logger.info(
            "list_search_results: conversation_id=%d count=%d min_fit=%s",
            self.conversation_id, len(results), min_fit,
        )
        return {"results": [r.to_dict() for r in results], "count": len(results)}
