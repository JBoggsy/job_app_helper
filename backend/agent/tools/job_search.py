"""job_search tool — job board API search via RapidAPI providers.

Supports three RapidAPI-based providers (all share the same API key):
  - JSearch: aggregated job listings from Google, Indeed, LinkedIn, etc.
  - Active Jobs DB (Fantastic.jobs): ATS/career-site jobs from 170k+ companies
  - LinkedIn Job Search (Fantastic.jobs): LinkedIn job postings
"""

import logging
import time
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
    provider: Optional[str] = Field(default=None, description="Provider: 'all' (default), 'jsearch', 'activejobs', or 'linkedin'")
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

# Maps our employment_type to Fantastic.jobs API format
_FANTASTIC_EMPLOYMENT_MAP = {
    "fulltime": "FULL_TIME",
    "parttime": "PART_TIME",
    "contract": "CONTRACTOR",
    "temporary": "TEMPORARY",
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


def _rapidapi_request(url, api_key, host, params, *, max_retries=3, timeout=30):
    """Make a RapidAPI GET request with retry on 429 and timeouts."""
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": host,
    }
    resp = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code == 429:
                if attempt < max_retries:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        "%s 429 rate-limited (attempt %d/%d), retrying in %ds…",
                        host, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
                    continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.ReadTimeout:
            if attempt < max_retries:
                logger.warning("%s timeout (attempt %d/%d), retrying…",
                               host, attempt + 1, max_retries)
                time.sleep(1)
                continue
            raise
    # All retries exhausted — raise for the last response
    if resp is not None:
        resp.raise_for_status()
    raise requests.exceptions.ConnectionError(f"Failed after {max_retries + 1} attempts to {host}")


def _check_rapidapi_error(data):
    """Check if a RapidAPI JSON response is an error/unsubscribed message.

    Some RapidAPI endpoints return HTTP 200 with a JSON body like
    ``{"message": "You are not subscribed..."}`` instead of an HTTP
    error code.  Detect these and raise so callers treat them as failures.
    """
    if isinstance(data, dict) and "message" in data and not any(
        k in data for k in ("data", "results", "jobs")
    ):
        raise RuntimeError(f"RapidAPI error: {data['message']}")


def _parse_fantastic_jobs(jobs, source_name, num_results):
    """Parse results from Fantastic.jobs APIs (Active Jobs DB / LinkedIn Job Search).

    Both APIs share the same response schema.
    """
    results = []
    for job in jobs:
        url = job.get("url") or ""
        if not url:
            continue

        # Build location from derived fields
        cities = job.get("cities_derived") or []
        regions = job.get("regions_derived") or []
        countries = job.get("countries_derived") or []
        loc_parts = []
        if cities and isinstance(cities[0], str):
            loc_parts.append(cities[0])
        if regions and isinstance(regions[0], str):
            loc_parts.append(regions[0])
        elif countries and isinstance(countries[0], str):
            loc_parts.append(countries[0])
        loc = ", ".join(loc_parts) if loc_parts else None

        posted = job.get("date_posted") or ""
        posted_date = posted[:10] if len(posted) >= 10 else None

        # Salary from raw or AI fields
        salary_raw = job.get("salary_raw") or {}
        sal_min = salary_raw.get("minValue") if isinstance(salary_raw, dict) else None
        sal_max = salary_raw.get("maxValue") if isinstance(salary_raw, dict) else None

        is_remote = job.get("remote_derived") or job.get("location_type") == "TELECOMMUTE"

        emp_types = job.get("employment_type") or []
        emp_type = emp_types[0].lower() if emp_types else None

        results.append(_normalize_result({
            "title": job.get("title"),
            "company": job.get("organization"),
            "location": loc,
            "url": url,
            "description": (job.get("description_text") or "")[:500],
            "salary_min": sal_min,
            "salary_max": sal_max,
            "remote": is_remote if is_remote else None,
            "employment_type": emp_type,
            "posted_date": posted_date,
            "source": source_name,
        }))

    return results[:num_results]


class JobSearchMixin:

    # -- JSearch --------------------------------------------------------

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

        resp = _rapidapi_request(
            "https://jsearch.p.rapidapi.com/search",
            self.rapidapi_key, "jsearch.p.rapidapi.com", params,
        )
        data = resp.json().get("data", [])

        results = []
        for job in data:
            url = job.get("job_apply_link") or ""
            if not url:
                continue

            city = job.get("job_city") or ""
            state = job.get("job_state") or ""
            loc_parts = [p for p in (city, state) if p]
            loc = ", ".join(loc_parts) if loc_parts else None

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

    # -- Active Jobs DB (Fantastic.jobs) --------------------------------

    def _search_active_jobs_db(self, query, location=None, remote_only=False,
                               salary_min=None, salary_max=None, num_results=10,
                               date_posted=None, employment_type=None, sort_by=None):
        """Query the Active Jobs DB (Fantastic.jobs) API on RapidAPI."""
        params = {
            "title_filter": f'"{query}"',
            "limit": str(min(num_results, 100)),
            "description_type": "text",
        }
        if location:
            params["location_filter"] = f'"{location}"'
        if remote_only:
            params["remote"] = "true"
        if employment_type and employment_type in _FANTASTIC_EMPLOYMENT_MAP:
            params["ai_employment_type_filter"] = _FANTASTIC_EMPLOYMENT_MAP[employment_type]

        resp = _rapidapi_request(
            "https://active-jobs-db.p.rapidapi.com/active-ats-7d",
            self.rapidapi_key, "active-jobs-db.p.rapidapi.com", params,
        )
        data = resp.json()
        _check_rapidapi_error(data)
        jobs = data if isinstance(data, list) else data.get("data", data.get("results", []))
        return _parse_fantastic_jobs(jobs, "activejobs", num_results)

    # -- LinkedIn Job Search (Fantastic.jobs) ---------------------------

    def _search_linkedin_jobs(self, query, location=None, remote_only=False,
                              salary_min=None, salary_max=None, num_results=10,
                              date_posted=None, employment_type=None, sort_by=None):
        """Query the LinkedIn Job Search (Fantastic.jobs) API on RapidAPI."""
        params = {
            "title_filter": f'"{query}"',
            "limit": str(min(num_results, 100)),
            "description_type": "text",
        }
        if location:
            params["location_filter"] = f'"{location}"'
        if remote_only:
            params["remote"] = "true"
        if employment_type and employment_type in _FANTASTIC_EMPLOYMENT_MAP:
            params["type_filter"] = _FANTASTIC_EMPLOYMENT_MAP[employment_type]

        resp = _rapidapi_request(
            "https://linkedin-job-search-api.p.rapidapi.com/active-jb-7d",
            self.rapidapi_key, "linkedin-job-search-api.p.rapidapi.com", params,
        )
        data = resp.json()
        _check_rapidapi_error(data)
        jobs = data if isinstance(data, list) else data.get("data", data.get("results", []))
        return _parse_fantastic_jobs(jobs, "linkedin", num_results)

    # -- Provider registry ----------------------------------------------

    _PROVIDERS = {
        "jsearch":    ("_search_jsearch",        "JSearch"),
        "activejobs": ("_search_active_jobs_db", "Active Jobs DB"),
        "linkedin":   ("_search_linkedin_jobs",  "LinkedIn Jobs"),
    }

    @agent_tool(
        description=(
            "Search job board APIs for real job listings. "
            "Uses RapidAPI-based providers: JSearch (Indeed/LinkedIn aggregator), "
            "Active Jobs DB (ATS/career-site jobs from 170k+ companies), and "
            "LinkedIn Job Search. Returns structured results with title, company, "
            "location, application URL, salary range, and more. "
            "Configure a RapidAPI key in Settings to enable."
        ),
        args_schema=JobSearchInput,
    )
    def job_search(self, query, location=None, remote_only=False,
                   salary_min=None, salary_max=None, num_results=10,
                   provider=None, date_posted=None, employment_type=None,
                   sort_by=None):
        num_results = min(num_results, 20)

        if not self.rapidapi_key:
            return {"error": "No RapidAPI key configured. Set a RapidAPI key in Settings → Integrations."}

        # Determine which providers to query
        if provider and provider in self._PROVIDERS:
            providers_to_use = [provider]
        else:
            # Default: use all three providers
            providers_to_use = list(self._PROVIDERS.keys())

        search_kwargs = dict(
            query=query, location=location, remote_only=remote_only,
            salary_min=salary_min, salary_max=salary_max,
            num_results=num_results, date_posted=date_posted,
            employment_type=employment_type, sort_by=sort_by,
        )

        all_results = []
        warnings = []
        provider_used = []

        for prov in providers_to_use:
            method_name, display_name = self._PROVIDERS[prov]
            method = getattr(self, method_name)
            try:
                logger.info("Querying %s for '%s'%s", display_name, query,
                            f" in {location}" if location else "")
                results = method(**search_kwargs)
                logger.info("%s returned %d result(s)", display_name, len(results))
                all_results.extend(results)
                provider_used.append(prov)
            except Exception as e:
                logger.exception("%s API error", display_name)
                warnings.append(f"{display_name} failed: {e}")

        if not provider_used:
            errors_str = "; ".join(warnings) if warnings else "Unknown error"
            return {"error": f"All job search providers failed: {errors_str}"}

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
            "provider": ",".join(provider_used),
            "total": len(deduped),
        }
        if warnings:
            result["warnings"] = warnings
        return result
