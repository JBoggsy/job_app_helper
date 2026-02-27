"""job_search tool — job board API search (JSearch/Adzuna)."""

import logging
from typing import Optional

import requests
from pydantic import BaseModel, Field

from ._registry import agent_tool

logger = logging.getLogger(__name__)


class JobSearchInput(BaseModel):
    query: str = Field(description="Job search keywords")
    location: Optional[str] = Field(default=None, description="Location filter (city, state, country)")
    remote_only: Optional[bool] = Field(default=False, description="Remote jobs only")
    salary_min: Optional[int] = Field(default=None, description="Minimum salary")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary")
    num_results: int = Field(default=10, description="Number of results (max 20)")
    provider: Optional[str] = Field(default=None, description="Provider: 'both' (default), 'jsearch', or 'adzuna'")
    date_posted: Optional[str] = Field(default=None, description="Recency filter: 'today', '3days', 'week', 'month'")
    employment_type: Optional[str] = Field(default=None, description="'fulltime', 'parttime', 'contract', 'temporary'")
    sort_by: Optional[str] = Field(default=None, description="'relevance' or 'date'")


# Maps our employment_type values to JSearch's expected format
_JSEARCH_EMPLOYMENT_MAP = {
    "fulltime": "FULLTIME",
    "parttime": "PARTTIME",
    "contract": "CONTRACTOR",
    "temporary": "INTERN",
}

# Maps our date_posted values to Adzuna's max_days_old
_ADZUNA_DATE_MAP = {
    "today": 1,
    "3days": 3,
    "week": 7,
    "month": 30,
}


def _normalize_result(result):
    """Ensure all result fields have the expected types."""
    return {
        "title": result.get("title") or "",
        "company": result.get("company") or "",
        "location": result.get("location"),
        "url": result.get("url") or "",
        "description": result.get("description") or "",
        "salary_min": result.get("salary_min"),
        "salary_max": result.get("salary_max"),
        "remote": result.get("remote"),
        "employment_type": result.get("employment_type"),
        "posted_date": result.get("posted_date"),
        "source": result.get("source", ""),
    }


class JobSearchMixin:

    def _search_jsearch(self, query, location=None, remote_only=False,
                        salary_min=None, salary_max=None, num_results=10,
                        date_posted=None, employment_type=None, sort_by=None):
        """Query the JSearch (RapidAPI) job search API."""
        search_query = query
        if location:
            search_query = f"{query} in {location}"

        params = {
            "query": search_query,
            "num_pages": "1",
        }
        if remote_only:
            params["remote_jobs_only"] = "true"
        if date_posted:
            params["date_posted"] = date_posted
        if employment_type and employment_type in _JSEARCH_EMPLOYMENT_MAP:
            params["employment_types"] = _JSEARCH_EMPLOYMENT_MAP[employment_type]

        headers = {
            "X-RapidAPI-Key": self.jsearch_api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        resp = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        results = []
        for job in data:
            url = job.get("job_apply_link") or ""
            if not url:
                continue

            # Build location string
            city = job.get("job_city") or ""
            state = job.get("job_state") or ""
            loc_parts = [p for p in (city, state) if p]
            loc = ", ".join(loc_parts) if loc_parts else None

            # Posted date
            posted = job.get("job_posted_at_datetime_utc") or ""
            posted_date = posted[:10] if len(posted) >= 10 else None

            results.append(_normalize_result({
                "title": job.get("job_title"),
                "company": job.get("employer_name"),
                "location": loc,
                "url": url,
                "description": (job.get("job_description") or "")[:500],
                "salary_min": job.get("job_min_salary"),
                "salary_max": job.get("job_max_salary"),
                "remote": job.get("job_is_remote"),
                "employment_type": (job.get("job_employment_type") or "").lower() or None,
                "posted_date": posted_date,
                "source": "jsearch",
            }))

        return results[:num_results]

    def _search_adzuna(self, query, location=None, remote_only=False,
                       salary_min=None, salary_max=None, num_results=10,
                       date_posted=None, employment_type=None, sort_by=None):
        """Query the Adzuna job search API."""
        country = getattr(self, "adzuna_country", "us") or "us"

        params = {
            "app_id": self.adzuna_app_id,
            "app_key": self.adzuna_app_key,
            "what": query,
            "results_per_page": min(num_results, 20),
        }
        if location:
            params["where"] = location
        if salary_min is not None:
            params["salary_min"] = salary_min
        if salary_max is not None:
            params["salary_max"] = salary_max
        if date_posted and date_posted in _ADZUNA_DATE_MAP:
            params["max_days_old"] = _ADZUNA_DATE_MAP[date_posted]
        if employment_type:
            if employment_type == "fulltime":
                params["full_time"] = 1
            elif employment_type == "parttime":
                params["part_time"] = 1
            elif employment_type == "contract":
                params["contract"] = 1
        if sort_by and sort_by in ("relevance", "date"):
            params["sort_by"] = sort_by

        resp = requests.get(
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("results", [])

        results = []
        for job in data:
            url = job.get("redirect_url") or ""
            if not url:
                continue

            # Posted date
            created = job.get("created") or ""
            posted_date = created[:10] if len(created) >= 10 else None

            results.append(_normalize_result({
                "title": job.get("title"),
                "company": (job.get("company") or {}).get("display_name"),
                "location": (job.get("location") or {}).get("display_name"),
                "url": url,
                "description": (job.get("description") or "")[:500],
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "remote": None,
                "employment_type": None,
                "posted_date": posted_date,
                "source": "adzuna",
            }))

        return results[:num_results]

    @agent_tool(
        description=(
            "Search job board APIs (JSearch, Adzuna) for real job listings. "
            "Returns structured results with title, company, location, application URL, "
            "salary range, and more. Configure API keys in Settings to enable providers."
        ),
        args_schema=JobSearchInput,
    )
    def job_search(self, query, location=None, remote_only=False,
                   salary_min=None, salary_max=None, num_results=10,
                   provider=None, date_posted=None, employment_type=None,
                   sort_by=None):
        num_results = min(num_results, 20)

        has_jsearch = bool(self.jsearch_api_key)
        has_adzuna = bool(self.adzuna_app_id and self.adzuna_app_key)

        # Determine which providers to query
        if provider == "jsearch":
            if not has_jsearch:
                return {"error": "JSearch API key not configured. Set JSEARCH_API_KEY or configure it in Settings."}
            use_jsearch, use_adzuna = True, False
        elif provider == "adzuna":
            if not has_adzuna:
                return {"error": "Adzuna API keys not configured. Set ADZUNA_APP_ID and ADZUNA_APP_KEY or configure them in Settings."}
            use_jsearch, use_adzuna = False, True
        else:
            # Default: use all configured providers
            use_jsearch = has_jsearch
            use_adzuna = has_adzuna

        if not use_jsearch and not use_adzuna:
            return {"error": "No job search API keys configured. Set up JSearch (JSEARCH_API_KEY) or Adzuna (ADZUNA_APP_ID + ADZUNA_APP_KEY) in Settings."}

        search_kwargs = dict(
            query=query, location=location, remote_only=remote_only,
            salary_min=salary_min, salary_max=salary_max,
            num_results=num_results, date_posted=date_posted,
            employment_type=employment_type, sort_by=sort_by,
        )

        all_results = []
        warnings = []
        provider_used = []

        if use_jsearch:
            try:
                jsearch_results = self._search_jsearch(**search_kwargs)
                all_results.extend(jsearch_results)
                provider_used.append("jsearch")
            except Exception as e:
                logger.exception("JSearch API error")
                if not use_adzuna:
                    return {"error": f"JSearch API error: {e}"}
                warnings.append(f"JSearch failed: {e}")

        if use_adzuna:
            try:
                adzuna_results = self._search_adzuna(**search_kwargs)
                all_results.extend(adzuna_results)
                provider_used.append("adzuna")
            except Exception as e:
                logger.exception("Adzuna API error")
                if not use_jsearch or not provider_used:
                    return {"error": f"Adzuna API error: {e}"}
                warnings.append(f"Adzuna failed: {e}")

        if not provider_used:
            return {"error": "All job search providers failed. Check your API keys and try again."}

        # Deduplicate by (company, title) — keep first occurrence
        seen = set()
        deduped = []
        for r in all_results:
            key = (r["company"].lower().strip(), r["title"].lower().strip())
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        deduped = deduped[:num_results]

        result = {
            "results": deduped,
            "provider": provider_used[0] if len(provider_used) == 1 else "both",
            "total": len(deduped),
        }
        if warnings:
            result["warnings"] = warnings
        return result
