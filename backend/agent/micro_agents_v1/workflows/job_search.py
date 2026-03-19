"""Job Search workflow — search job boards and return a curated list.

Pipeline:
1. A DSPy module generates 4-10 diverse search queries (full API param
   sets) from the user's request, expanding vague terms (e.g. "in the
   south" → GA, NC, SC, FL, etc.).
2. Queries are executed programmatically via the ``job_search`` and/or
   ``web_search`` tools.
3. Results are de-duplicated (by URL and company+title).
4. A DSPy evaluator scores each job on a 0-5 star scale with a short
   fit explanation, using the user's profile for context.
5. Jobs scoring < 3 stars are filtered out.
6. A DSPy module verifies/fixes the URL of preliminarily qualifying jobs
   to be the most direct listing link.
7. Qualifying jobs are added as search results via ``add_search_result``.

Rate-limit note: a 1-second delay is inserted between consecutive
job_search API calls to avoid 429 errors from JSearch/RapidAPI.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
from urllib.parse import urlparse

import dspy
import requests as http_requests
from pydantic import BaseModel, Field

from backend.agent.tools import AgentTools
from backend.llm.llm_factory import LLMConfig

from ._dspy_utils import build_lm
from .registry import BaseWorkflow, WorkflowResult, register_workflow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Evaluation rubric — stored separately so it can be updated/generated
# independently from the system prompts.
# ---------------------------------------------------------------------------

JOB_FIT_RUBRIC = """\
Score each job on a 0-5 star scale based on how well it matches the
candidate's profile.  Use the following criteria:

**5 stars — Excellent fit**
- Role title and seniority closely match the candidate's experience level.
- Required skills are a strong subset of the candidate's skills.
- Location/remote preferences are satisfied.
- Salary range (if known) aligns with the candidate's expectations.

**4 stars — Good fit**
- Most requirements match; minor gaps the candidate could reasonably
  bridge (e.g. a "nice-to-have" technology they haven't used).
- Location or salary is acceptable but not ideal.

**3 stars — Moderate fit**
- The core role is relevant, but there are notable gaps (missing a key
  required skill, seniority mismatch of ~1 level, or location is a
  stretch).
- Still worth the candidate reviewing.

**2 stars — Weak fit**
- Significant mismatches in multiple dimensions (skills, seniority,
  location, or domain).
- Unlikely to be a productive application.

**1 star — Poor fit**
- The role is tangentially related at best; most requirements do not
  align with the candidate's background.

**0 stars — No fit**
- Completely unrelated role, wrong field, or the listing is clearly
  spam/irrelevant.

When the candidate's profile is sparse or missing, be generous (default
toward 3) but still penalise obvious mismatches with the search request
itself (e.g. a nursing job when the user asked for software engineering
roles).

Always provide a 1-2 sentence ``fit_reason`` explaining the score.
"""


# ---------------------------------------------------------------------------
# DSPy signatures & Pydantic models
# ---------------------------------------------------------------------------


class SearchQuery(BaseModel):
    """A single job-search API query with fully expanded parameters."""

    query: str = Field(
        description=(
            "SHORT job-search query string — 2 to 5 words max. Use a "
            "simple job title or a job title plus ONE qualifier. Do NOT "
            "pack multiple skills or buzzwords into one query; that "
            "produces overly specific searches with zero results. "
            "GOOD: 'ML Research Engineer', 'Applied Scientist', "
            "'Computer Vision Engineer', 'Data Scientist NLP'. "
            "BAD: 'AI Research Scientist computer vision world models PhD', "
            "'ML Engineer reinforcement learning robotics startup'."
        )
    )
    location: Optional[str] = Field(
        default=None,
        description=(
            "A specific city, state, or country. Vague regions must be "
            "expanded into individual locations across separate queries — "
            "e.g. 'the south' becomes separate queries for Atlanta GA, "
            "Charlotte NC, Nashville TN, Miami FL, etc. Never pass a "
            "vague region name here."
        ),
    )
    remote_only: bool = Field(default=False, description="True if remote-only jobs requested")
    salary_min: Optional[int] = Field(default=None, description="Minimum salary filter")
    salary_max: Optional[int] = Field(default=None, description="Maximum salary filter")
    num_results: int = Field(default=10, description="Number of results to request (max 20)")
    date_posted: Optional[str] = Field(
        default=None,
        description="Recency filter: 'today', '3days', 'week', 'month'",
    )
    employment_type: Optional[str] = Field(
        default=None,
        description="'fulltime', 'parttime', 'contract', 'temporary'",
    )


class GenerateSearchQueriesSig(dspy.Signature):
    """Generate diverse job-search API queries from the user's request.

    You produce 4-10 query parameter sets that, taken together, cast a
    wide net over the user's intent.  Each query hits a different angle
    (title synonym, adjacent role, broader category).

    QUERY LENGTH RULES (CRITICAL — read carefully):
    - Each query string MUST be 2-5 words.  Typically just a job title,
      or a job title plus ONE modifier.
    - NEVER cram multiple skills, buzzwords, or qualifiers into one
      query.  Job-search APIs treat multi-word strings as exact-match
      phrases — the more words you add, the fewer results you get.
    - GOOD examples: "ML Research Engineer", "Applied Scientist",
      "Computer Vision Engineer", "Data Scientist", "AI Engineer",
      "Research Scientist ML", "NLP Engineer".
    - BAD examples: "AI Research Scientist computer vision world models
      PhD", "Machine Learning Engineer reinforcement learning agents".
    - Achieve breadth by using DIFFERENT short queries, NOT by stuffing
      keywords into fewer queries.

    Expansion rules:
    - **Geography:** Vague regions MUST be expanded into multiple queries
      with specific cities/states.  "The south" → separate queries for
      Atlanta GA, Charlotte NC, Nashville TN, Austin TX, Miami FL, etc.
      "The Bay Area" → San Francisco CA, San Jose CA, Oakland CA.
      "The Midwest" → Chicago IL, Minneapolis MN, Detroit MI, etc.
    - **Company descriptions:** Never search for abstract descriptions.
      "Early-stage startups" → vary the job-title keywords instead
      (e.g. "founding engineer", "software engineer startup").
    - **Role variations:** Broaden with synonyms and related titles.
      "Data scientist" → also try "ML engineer", "applied scientist",
      "data analyst" as separate short queries.
    """

    user_request: str = dspy.InputField(
        desc="The user's natural-language job search request"
    )
    user_profile: str = dspy.InputField(
        desc="The user's job search profile (skills, preferences, experience) — may be empty"
    )
    queries: list[SearchQuery] = dspy.OutputField(
        desc="4-10 diverse, concrete API query parameter sets"
    )


class JobFitScore(BaseModel):
    """Evaluation result for a single job."""

    job_index: int = Field(description="0-based index into the jobs list")
    score: int = Field(description="Fit score 0-5")
    fit_reason: str = Field(description="1-2 sentence explanation of the score")


class EvaluateJobFitSig(dspy.Signature):
    """Score a batch of jobs against the candidate's profile.

    Use the provided rubric to assign each job a 0-5 star score and a
    short fit explanation.
    """

    jobs_json: str = dspy.InputField(
        desc="JSON list of job objects (title, company, description, requirements, etc.)"
    )
    user_profile: str = dspy.InputField(
        desc="The candidate's profile (skills, experience, preferences)"
    )
    user_request: str = dspy.InputField(
        desc="The original search request for additional context"
    )
    rubric: str = dspy.InputField(
        desc="Scoring rubric to follow"
    )
    scores: list[JobFitScore] = dspy.OutputField(
        desc="One score entry per job, referencing jobs by index"
    )


class UrlVerification(BaseModel):
    """Verification result for a single job's URL."""

    job_index: int = Field(description="0-based index into the jobs list")
    status: str = Field(
        description=(
            "One of: 'valid' (URL is the original posting and appears live), "
            "'replaced' (found a better direct URL), "
            "'dead' (listing is closed, expired, or does not exist)"
        )
    )
    verified_url: Optional[str] = Field(
        default=None,
        description="The verified or replacement URL (null if dead)",
    )
    reason: str = Field(description="Brief explanation of the verification outcome")


class VerifyJobUrlsSig(dspy.Signature):
    """Verify and improve job listing URLs.

    For each job, you are given the original URL and the scraped page
    content (if available).  Determine whether the URL points to the
    original job posting on the employer's own careers page (which may
    be hosted via providers like Greenhouse, Lever, Workday, etc.) or
    to a third-party aggregator (Indeed, ZipRecruiter, SimplyHired,
    LinkedIn re-posts, Glassdoor listings, etc.).

    Additionally detect dead/closed/expired listings.

    Guidelines:
    - If the page content clearly shows the job is closed, expired, or
      a 404 / "job not found" page, mark it ``dead``.
    - If the URL is on an aggregator but the page content contains a
      direct link to the employer's careers page or an ATS (Greenhouse,
      Lever, Workday, Ashby, BambooHR, iCIMS, etc.), extract that link
      and mark it ``replaced``.
    - If no better URL can be found from the provided information and
      web search results, but the listing appears live, mark it
      ``valid``.
    - Prefer ATS-hosted URLs (e.g. boards.greenhouse.io/company/jobs/ID)
      over generic aggregator pages.
    """

    jobs_json: str = dspy.InputField(
        desc="JSON list of job objects with 'url', 'title', 'company', and 'scraped_content' fields"
    )
    web_search_results: str = dspy.InputField(
        desc="JSON list of web search results for finding direct posting URLs (may be empty)"
    )
    verifications: list[UrlVerification] = dspy.OutputField(
        desc="One verification entry per job"
    )


# ---------------------------------------------------------------------------
# Aggregator domain detection
# ---------------------------------------------------------------------------

AGGREGATOR_DOMAINS = frozenset({
    "indeed.com", "ziprecruiter.com", "simplyhired.com", "glassdoor.com",
    "monster.com", "careerbuilder.com", "dice.com", "snagajob.com",
    "jooble.org", "neuvoo.com", "talent.com", "adzuna.com",
    "linkedin.com", "google.com",
})


def _is_aggregator_url(url: str) -> bool:
    """Return True if the URL belongs to a known job-aggregator domain."""
    try:
        host = urlparse(url).hostname or ""
        # Strip www. prefix
        host = host.removeprefix("www.")
        # Check against known aggregators (match base domain)
        for agg in AGGREGATOR_DOMAINS:
            if host == agg or host.endswith("." + agg):
                return True
    except Exception:
        pass
    return False


# Phrases in page bodies that indicate a listing is dead/closed.
# Checked case-insensitively against the first ~5 KB of response text.
_DEAD_LISTING_PHRASES = [
    "this position has been filled",
    "this job has expired",
    "this job is no longer available",
    "this job posting has been removed",
    "no longer accepting applications",
    "this position is no longer available",
    "this listing has expired",
    "job not found",
    "the job you are looking for is no longer available",
    "this role has been filled",
    "posting has closed",
    "this requisition is no longer active",
    "application deadline has passed",
]

# HTTP status codes that indicate a dead URL.
_DEAD_HTTP_STATUSES = frozenset({404, 410, 451})

# Timeout for lightweight liveness checks (seconds).
_LIVENESS_TIMEOUT = 8


def _check_url_liveness(url: str) -> tuple[bool, str]:
    """Do a lightweight HTTP GET to check if a URL is alive.

    Returns ``(is_alive, snippet)`` where *snippet* is the first ~5 KB
    of the response body (useful for dead-listing phrase matching) or an
    empty string on failure.

    This does NOT use Tavily — it's a direct HTTP request, so it's free.
    """
    if not url:
        return False, ""
    try:
        resp = http_requests.get(
            url,
            timeout=_LIVENESS_TIMEOUT,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            allow_redirects=True,
        )
        if resp.status_code in _DEAD_HTTP_STATUSES:
            return False, ""
        # Grab a snippet of the body for phrase-based checks
        snippet = resp.text[:5000].lower()
        for phrase in _DEAD_LISTING_PHRASES:
            if phrase in snippet:
                return False, snippet
        return True, snippet
    except http_requests.RequestException:
        # Connection error / timeout — treat as dead
        return False, ""


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@register_workflow("job_search")
class JobSearchWorkflow(BaseWorkflow):
    """Find new job openings by searching job boards and the web, scoring each result for fit against the user's profile, and returning curated search results."""

    OUTPUTS = {
        "added": "int — number of qualifying jobs added as search results",
        "total_searched": "int — total unique results found across all queries",
        "queries_run": "int — number of search queries executed",
    }

    #: Default number of jobs sent to the evaluator LLM in one call.
    #: Override at runtime via ``self.params["eval_batch_size"]``.
    EVAL_BATCH_SIZE: int = 15

    # -- Step 1: Generate search queries --------------------------------

    def _generate_queries(
        self, user_request: str, user_profile: str,
    ) -> list[dict]:
        """Use DSPy to produce diverse, expanded search queries."""
        lm = build_lm(self.llm_config)
        generator = dspy.ChainOfThought(GenerateSearchQueriesSig)

        with dspy.context(lm=lm):
            result = generator(
                user_request=user_request,
                user_profile=user_profile,
            )

        queries = []
        for sq in result.queries:
            q: dict = {"query": sq.query, "num_results": sq.num_results}
            if sq.location:
                q["location"] = sq.location
            if sq.remote_only:
                q["remote_only"] = True
            if sq.salary_min is not None:
                q["salary_min"] = sq.salary_min
            if sq.salary_max is not None:
                q["salary_max"] = sq.salary_max
            if sq.date_posted:
                q["date_posted"] = sq.date_posted
            if sq.employment_type:
                q["employment_type"] = sq.employment_type
            queries.append(q)

        return queries

    # -- Step 2: Execute queries ----------------------------------------

    def _execute_queries(
        self, queries: list[dict],
    ) -> list[dict]:
        """Run each query via the job_search tool, collecting raw results."""
        all_results: list[dict] = []

        for i, q in enumerate(queries, 1):
            # Throttle to avoid 429 rate-limit errors from JSearch/RapidAPI
            if i > 1:
                time.sleep(1)

            self.event_bus.emit("text_delta", {
                "content": f"  Running query {i}/{len(queries)}: "
                f"\"{q['query']}\""
                + (f" in {q['location']}" if q.get("location") else "")
                + "...\n",
            })

            resp = self.tools.execute("job_search", q)
            if "error" in resp:
                logger.warning("job_search query failed: %s", resp["error"])
                self.event_bus.emit("text_delta", {"content": f"    (query failed: {resp['error']})\n"})
                continue

            results = resp.get("results", [])
            all_results.extend(results)
            logger.info("Query %d returned %d results", i, len(results))

        return all_results

    # -- Step 3: Deduplicate --------------------------------------------

    @staticmethod
    def _deduplicate(results: list[dict]) -> list[dict]:
        """Remove duplicates by URL first, then by (company, title)."""
        seen_urls: set[str] = set()
        seen_keys: set[tuple[str, str]] = set()
        unique: list[dict] = []

        for r in results:
            url = (r.get("url") or "").strip()
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)

            company = (r.get("company") or "").strip().lower()
            title = (r.get("title") or "").strip().lower()
            key = (company, title)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            unique.append(r)

        return unique

    # -- Step 4-5: Evaluate fit and filter ------------------------------

    def _evaluate_and_filter(
        self, jobs: list[dict], user_profile: str, user_request: str,
    ) -> list[dict]:
        """Score each job and filter out those below the threshold."""
        if not jobs:
            return []

        self.event_bus.emit("text_delta", {"content": f"Evaluating fit for {len(jobs)} unique results...\n"})

        # Build a trimmed version for the LLM (avoid huge payloads)
        trimmed = []
        for j in jobs:
            trimmed.append({
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": j.get("location"),
                "description": (j.get("description") or "")[:1500],
                "salary_min": j.get("salary_min"),
                "salary_max": j.get("salary_max"),
                "remote": j.get("remote"),
                "employment_type": j.get("employment_type"),
            })

        batch_size = int(self.params.get("eval_batch_size", self.EVAL_BATCH_SIZE))
        scored_jobs: list[dict] = []

        for batch_start in range(0, len(jobs), batch_size):
            batch_jobs = jobs[batch_start : batch_start + batch_size]
            batch_trimmed = trimmed[batch_start : batch_start + batch_size]

            lm = build_lm(self.llm_config)
            evaluator = dspy.ChainOfThought(EvaluateJobFitSig)

            with dspy.context(lm=lm):
                result = evaluator(
                    jobs_json=json.dumps(batch_trimmed, default=str),
                    user_profile=user_profile,
                    user_request=user_request,
                    rubric=JOB_FIT_RUBRIC,
                )

            # Map scores back to jobs
            score_map: dict[int, JobFitScore] = {}
            for s in result.scores:
                score_map[s.job_index] = s

            for i, job in enumerate(batch_jobs):
                score_entry = score_map.get(i)
                if score_entry and score_entry.score >= 3:
                    scored_jobs.append({
                        **job,
                        "_fit_score": score_entry.score,
                        "_fit_reason": score_entry.fit_reason,
                    })

        self.event_bus.emit("text_delta", {
            "content": f"  {len(scored_jobs)} of {len(jobs)} jobs scored 3+ stars.\n",
        })

        return scored_jobs

    # -- Step 6: Verify/fix URLs ----------------------------------------

    def _liveness_check(
        self, jobs: list[dict],
    ) -> tuple[list[dict], int]:
        """Tier 1: lightweight HTTP liveness check for ALL URLs.

        Returns ``(surviving_jobs, dead_count)``.  This uses direct HTTP
        requests (no Tavily API cost).
        """
        self.event_bus.emit("text_delta", {"content": f"  Checking liveness of {len(jobs)} URL(s)...\n"})

        alive: list[dict] = []
        dead_count = 0

        for job in jobs:
            url = job.get("url") or ""
            if not url:
                # No URL — keep it, will try to find one in tier 2
                alive.append(job)
                continue

            is_alive, _snippet = _check_url_liveness(url)
            if is_alive:
                alive.append(job)
            else:
                dead_count += 1
                logger.info(
                    "Dead URL (liveness check): %s — %s at %s",
                    url, job.get("title"), job.get("company"),
                )

        if dead_count:
            self.event_bus.emit("text_delta", {
                "content": f"  Filtered {dead_count} dead/unreachable URL(s).\n",
            })

        return alive, dead_count

    def _resolve_aggregator_urls(
        self, jobs: list[dict],
    ) -> list[dict]:
        """Tier 2: for jobs on aggregator domains, use Tavily scrape +
        web search to find direct employer posting URLs.

        Only called for jobs that survived the liveness check.
        """
        aggregator_indices: list[int] = []
        for i, job in enumerate(jobs):
            url = job.get("url") or ""
            if _is_aggregator_url(url) or not url:
                aggregator_indices.append(i)

        if not aggregator_indices:
            return jobs

        self.event_bus.emit("text_delta", {
            "content": (
                f"  Resolving direct URLs for {len(aggregator_indices)} "
                f"aggregator link(s)...\n"
            ),
        })

        # Scrape aggregator pages for direct links
        jobs_for_verification: list[dict] = []
        for i in aggregator_indices:
            job = jobs[i]
            url = job.get("url") or ""
            scraped_content = ""

            if url:
                scrape_resp = self.tools.execute("scrape_url", {
                    "url": url,
                    "query": f"{job.get('title', '')} {job.get('company', '')} careers apply",
                })
                if "error" not in scrape_resp:
                    scraped_content = scrape_resp.get("content", "")

            jobs_for_verification.append({
                "index": i,
                "url": url,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "scraped_content": scraped_content[:3000],
            })

        # Web-search for direct career page URLs
        web_results_all: list[dict] = []
        for item in jobs_for_verification:
            search_query = (
                f"{item['company']} {item['title']} careers apply"
            )
            ws_resp = self.tools.execute("web_search", {
                "query": search_query,
                "num_results": 3,
            })
            if "error" not in ws_resp:
                for wr in ws_resp.get("results", []):
                    web_results_all.append({
                        "job_index": item["index"],
                        "title": wr.get("title", ""),
                        "url": wr.get("url", ""),
                        "content": (wr.get("content") or "")[:500],
                    })

        # Run DSPy verification to extract direct URLs
        lm = build_lm(self.llm_config)
        verifier = dspy.ChainOfThought(VerifyJobUrlsSig)

        with dspy.context(lm=lm):
            result = verifier(
                jobs_json=json.dumps(jobs_for_verification, default=str),
                web_search_results=json.dumps(web_results_all, default=str),
            )

        # Apply verification results
        dead_indices: set[int] = set()
        replaced_count = 0
        for v in result.verifications:
            idx = v.job_index
            if idx < 0 or idx >= len(jobs):
                continue
            if v.status == "dead":
                dead_indices.add(idx)
                logger.info(
                    "Filtering dead listing (DSPy): %s at %s — %s",
                    jobs[idx].get("title"), jobs[idx].get("company"), v.reason,
                )
            elif v.status == "replaced" and v.verified_url:
                old_url = jobs[idx].get("url", "")
                jobs[idx]["url"] = v.verified_url
                replaced_count += 1
                logger.info(
                    "Replaced URL for %s at %s: %s → %s",
                    jobs[idx].get("title"), jobs[idx].get("company"),
                    old_url, v.verified_url,
                )

        verified = [j for i, j in enumerate(jobs) if i not in dead_indices]

        parts: list[str] = []
        if replaced_count:
            parts.append(f"upgraded {replaced_count} to direct link(s)")
        if dead_indices:
            parts.append(f"removed {len(dead_indices)} dead listing(s)")
        if parts:
            self.event_bus.emit("text_delta", {"content": f"  {'; '.join(parts).capitalize()}.\n"})

        return verified

    def _verify_urls(
        self, jobs: list[dict],
    ) -> list[dict]:
        """Two-tier URL verification.

        Tier 1 (all URLs, free): lightweight HTTP GET to detect dead
        links, 404s, and pages containing "this job has expired"-style
        text.

        Tier 2 (aggregator URLs, Tavily API): scrape + web search to
        find the direct employer posting and replace aggregator links.
        """
        if not jobs:
            return []

        # Tier 1: liveness check (free HTTP requests)
        alive, dead_count = self._liveness_check(jobs)
        if not alive:
            return []

        # Tier 2: resolve aggregator URLs (uses Tavily for scraping)
        verified = self._resolve_aggregator_urls(alive)

        return verified

    # -- Step 7: Add search results -------------------------------------

    def _add_search_results(
        self, jobs: list[dict],
    ) -> int:
        """Add qualifying jobs as search results via the tool."""
        added = 0
        for job in jobs:
            remote_type = None
            if job.get("remote") is True:
                remote_type = "remote"

            params = {
                "company": job.get("company", "Unknown"),
                "title": job.get("title", "Unknown"),
                "job_fit": job.get("_fit_score", 3),
                "fit_reason": job.get("_fit_reason", ""),
            }
            if job.get("url"):
                params["url"] = job["url"]
            if job.get("salary_min") is not None:
                params["salary_min"] = job["salary_min"]
            if job.get("salary_max") is not None:
                params["salary_max"] = job["salary_max"]
            if job.get("location"):
                params["location"] = job["location"]
            if remote_type:
                params["remote_type"] = remote_type
            if job.get("source"):
                params["source"] = job["source"]
            if job.get("description"):
                params["description"] = job["description"][:2000]

            resp = self.tools.execute("add_search_result", params)
            if "error" in resp:
                logger.warning(
                    "Failed to add search result for %s at %s: %s",
                    job.get("title"), job.get("company"), resp["error"],
                )
            else:
                added += 1

        return added

    # -- Main run -------------------------------------------------------

    def run(self) -> WorkflowResult:
        user_request = self.outcome_description or self.params.get("user_message", "")

        self.event_bus.emit("text_delta", {"content": f"Searching for jobs: *{user_request}*\n\n"})

        # Load user profile
        profile_resp = self.tools.execute("read_user_profile", {})
        user_profile = profile_resp.get("content", "")

        # 1. Generate diverse search queries
        self.event_bus.emit("text_delta", {"content": "Generating search queries...\n"})
        try:
            queries = self._generate_queries(user_request, user_profile)
        except Exception as e:
            logger.exception("Failed to generate search queries")
            msg = f"Failed to generate search queries: {e}\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": str(e)},
                summary=msg.strip(),
            )

        if not queries:
            msg = "Could not generate any search queries from the request.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No queries generated"},
                summary=msg.strip(),
            )

        self.event_bus.emit("text_delta", {"content": f"Generated {len(queries)} search queries.\n"})

        # 2. Execute queries
        raw_results = self._execute_queries(queries)
        if not raw_results:
            msg = "No results found from any search query.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No search results"},
                summary=msg.strip(),
            )

        self.event_bus.emit("text_delta", {"content": f"\nCollected {len(raw_results)} raw results.\n"})

        # 3. Deduplicate
        unique_results = self._deduplicate(raw_results)
        self.event_bus.emit("text_delta", {
            "content": f"After deduplication: {len(unique_results)} unique jobs.\n\n",
        })

        # 4-5. Evaluate fit and filter
        qualifying = self._evaluate_and_filter(
            unique_results, user_profile, user_request,
        )

        if not qualifying:
            msg = (
                "None of the results scored 3+ stars for your profile. "
                "Try broadening your search criteria.\n"
            )
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "No qualifying results", "total_searched": len(unique_results)},
                summary=msg.strip(),
            )

        # 6. Verify/fix URLs
        self.event_bus.emit("text_delta", {"content": "\nVerifying job listing URLs...\n"})
        verified = self._verify_urls(qualifying)

        if not verified:
            msg = "All qualifying listings appear to be closed or dead.\n"
            self.event_bus.emit("text_delta", {"content": msg})
            return WorkflowResult(
                outcome_id=self.outcome_id,
                success=False,
                data={"error": "All listings dead", "total_searched": len(unique_results)},
                summary=msg.strip(),
            )

        # 7. Add as search results
        self.event_bus.emit("text_delta", {"content": f"\nAdding {len(verified)} job(s) to search results...\n"})
        added_count = self._add_search_results(verified)

        summary = (
            f"Found {added_count} qualifying job(s) from "
            f"{len(unique_results)} total results."
        )
        self.event_bus.emit("text_delta", {"content": f"\n{summary}\n"})

        return WorkflowResult(
            outcome_id=self.outcome_id,
            success=True,
            data={
                "added": added_count,
                "total_searched": len(unique_results),
                "queries_run": len(queries),
            },
            summary=summary,
        )
