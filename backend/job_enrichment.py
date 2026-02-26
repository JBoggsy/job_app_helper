"""Job enrichment — scrape a job URL and extract structured fields via LLM.

When a job is added to the tracker (from search results or via the agent),
this module scrapes the posting URL and uses an LLM to fill in any missing
fields so the tracker entry is as complete as possible.
"""

import json
import logging
import random
import re
import time

import cloudscraper
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Fields that can be enriched from a scraped job posting
ENRICHABLE_FIELDS = [
    "salary_min", "salary_max", "location", "remote_type",
    "requirements", "nice_to_haves", "tags", "source",
]

JOB_ENRICHMENT_PROMPT = """You are a job posting data extractor. Given the raw text scraped from a job posting, extract structured data to fill in missing fields.

## Existing Job Data (already known)
{existing_data}

## Instructions
Extract ONLY the fields that are currently missing (null/empty) from the existing data. Do not overwrite fields that already have values.

Return a JSON object with ONLY the fields you can confidently extract from the scraped text. Use these field names and formats:

- "salary_min": integer (annual salary in USD, e.g., 120000). Convert hourly/monthly to annual.
- "salary_max": integer (annual salary in USD, e.g., 180000). Convert hourly/monthly to annual.
- "location": string (city, state or region, e.g., "San Francisco, CA" or "New York, NY")
- "remote_type": string — one of "remote", "hybrid", or "onsite"
- "requirements": string — key requirements/qualifications as a newline-separated list
- "nice_to_haves": string — nice-to-have qualifications as a newline-separated list
- "tags": string — comma-separated relevant tags (e.g., "python,react,aws,startup")
- "source": string — the employer/platform name if identifiable (e.g., "LinkedIn", "Greenhouse", "Lever")

Only include fields where you have reasonable confidence from the scraped text. Omit fields you cannot determine. Return valid JSON only, no markdown fences or extra text."""


# ---------------------------------------------------------------------------
# Scraping utilities (mirrors AgentTools scraping logic)
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
]


def _build_browser_headers(ua):
    """Build realistic browser headers."""
    is_chrome = "Chrome" in ua
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    if is_chrome:
        headers["Sec-CH-UA"] = '"Chromium";v="133", "Not(A:Brand";v="99", "Google Chrome";v="133"'
        headers["Sec-CH-UA-Mobile"] = "?0"
        headers["Sec-CH-UA-Platform"] = '"Windows"' if "Windows" in ua else '"macOS"' if "Mac" in ua else '"Linux"'
    return headers


def _extract_text(html):
    """Parse HTML and return clean text content."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _scrape_with_cloudscraper(url):
    """Scrape using cloudscraper with realistic headers and retry logic."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    for attempt in range(3):
        try:
            ua = random.choice(_USER_AGENTS)
            headers = _build_browser_headers(ua)
            if attempt > 0:
                time.sleep(1.5 + random.random() * 2)
            resp = scraper.get(url, timeout=20, headers=headers)
            resp.raise_for_status()
            return _extract_text(resp.text)
        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None) or getattr(e, "status_code", None)
            logger.info("enrich scrape attempt %d failed (%s) for %s", attempt + 1, status or e, url)
            if attempt == 2:
                logger.warning("enrich scrape exhausted retries for %s", url)
    return None


def _scrape_with_tavily(url, search_api_key):
    """Fallback: use Tavily Extract API to fetch page content."""
    try:
        resp = requests.post(
            "https://api.tavily.com/extract",
            json={"urls": url, "extract_depth": "basic"},
            headers={"Authorization": f"Bearer {search_api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if results and results[0].get("raw_content"):
            logger.info("enrich: Tavily extract succeeded for %s", url)
            return results[0]["raw_content"]
        logger.info("enrich: Tavily extract returned empty for %s", url)
    except Exception as e:
        logger.warning("enrich: Tavily extract failed for %s: %s", url, e)
    return None


def scrape_url(url, search_api_key=""):
    """Scrape a URL and return text content, or None on failure."""
    logger.info("enrich: scraping %s", url)
    text = _scrape_with_cloudscraper(url)
    if text is None and search_api_key:
        text = _scrape_with_tavily(url, search_api_key)
    if text and len(text) > 6000:
        text = text[:6000]
    return text


# ---------------------------------------------------------------------------
# LLM-based field extraction
# ---------------------------------------------------------------------------

def _extract_json(text):
    """Extract a JSON object from LLM output, handling markdown fences."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    return None


def _fields_needing_enrichment(job_data):
    """Return the list of ENRICHABLE_FIELDS that are missing/empty in job_data."""
    missing = []
    for field in ENRICHABLE_FIELDS:
        val = job_data.get(field)
        if val is None or val == "" or val == 0:
            missing.append(field)
    return missing


def enrich_job_data(job_data, scraped_text=None, url=None, search_api_key="", llm_model=None):
    """Enrich a job data dict by scraping its URL and using an LLM to extract fields.

    This is the main entry point. It:
    1. Checks which fields are missing
    2. Scrapes the URL if scraped_text is not already provided
    3. Uses the LLM to extract missing fields from the scraped content
    4. Merges extracted fields into job_data (without overwriting existing values)

    Args:
        job_data: Dict of current job fields (company, title, url, salary_min, etc.)
        scraped_text: Pre-scraped page text (skips scraping if provided)
        url: URL to scrape (falls back to job_data["url"] if not provided)
        search_api_key: Tavily API key for fallback scraping
        llm_model: A LangChain BaseChatModel instance for extraction. If None, skips LLM.

    Returns:
        Dict with the enriched job_data (original + newly extracted fields).
        Also includes "_enrichment_status" key: "enriched", "no_url", "scrape_failed", "no_llm", or "skipped".
    """
    url = url or job_data.get("url")
    missing_fields = _fields_needing_enrichment(job_data)

    if not missing_fields:
        logger.info("enrich: all fields already populated, skipping")
        return {**job_data, "_enrichment_status": "skipped"}

    if not url:
        logger.info("enrich: no URL provided, cannot scrape")
        return {**job_data, "_enrichment_status": "no_url"}

    # Scrape the URL if needed
    if scraped_text is None:
        scraped_text = scrape_url(url, search_api_key)

    if not scraped_text:
        logger.warning("enrich: failed to scrape %s", url)
        return {**job_data, "_enrichment_status": "scrape_failed"}

    if llm_model is None:
        logger.info("enrich: no LLM model available, skipping extraction")
        return {**job_data, "_enrichment_status": "no_llm"}

    # Build existing data summary for the prompt
    existing_summary_parts = []
    for key, val in job_data.items():
        if key.startswith("_"):
            continue
        if val is not None and val != "" and val != 0:
            existing_summary_parts.append(f"- {key}: {val}")
        else:
            existing_summary_parts.append(f"- {key}: (missing)")
    existing_summary = "\n".join(existing_summary_parts)

    prompt_text = JOB_ENRICHMENT_PROMPT.format(existing_data=existing_summary)

    from langchain_core.messages import SystemMessage, HumanMessage

    lc_messages = [
        SystemMessage(content=prompt_text),
        HumanMessage(content=f"## Scraped Job Posting Text\n\n{scraped_text}"),
    ]

    try:
        logger.info("enrich: invoking LLM for field extraction (%d chars of scraped text)", len(scraped_text))
        response = llm_model.invoke(lc_messages)
        response_text = response.content if isinstance(response.content, str) else str(response.content)
        extracted = _extract_json(response_text)

        if not extracted or not isinstance(extracted, dict):
            logger.warning("enrich: LLM did not return valid JSON")
            return {**job_data, "_enrichment_status": "scrape_failed"}

        # Merge extracted fields (only fill in missing ones)
        enriched = dict(job_data)
        fields_filled = []
        for field in ENRICHABLE_FIELDS:
            if field in extracted and extracted[field] is not None:
                current = enriched.get(field)
                if current is None or current == "" or current == 0:
                    enriched[field] = extracted[field]
                    fields_filled.append(field)

        logger.info("enrich: filled %d fields: %s", len(fields_filled), fields_filled)
        enriched["_enrichment_status"] = "enriched"
        enriched["_fields_enriched"] = fields_filled
        return enriched

    except Exception as e:
        logger.error("enrich: LLM extraction failed: %s", e)
        return {**job_data, "_enrichment_status": "scrape_failed"}
