"""scrape_url tool — fetch and return plain text from a web page."""

from typing import Optional

from pydantic import BaseModel, Field
from tavily import TavilyClient

from ._registry import agent_tool


class ScrapeUrlInput(BaseModel):
    url: str = Field(description="The URL to scrape")
    query: Optional[str] = Field(
        default=None,
        description="Optional query used to re-rank the extracted content for relevance",
    )


class ScrapeUrlMixin:
    @agent_tool(
        description="Scrape a web page and return its text content.",
        args_schema=ScrapeUrlInput,
    )
    def scrape_url(self, url, query=None):
        if not self.search_api_key:
            return {"error": "No Tavily API key configured. Set SEARCH_API_KEY or configure it in Settings."}
        client = TavilyClient(api_key=self.search_api_key)
        kwargs = {"extract_depth": "advanced"}
        if query:
            kwargs["query"] = query
        response = client.extract(urls=url, **kwargs)
        results = response.get("results", [])
        if not results:
            return {"error": f"Failed to extract content from {url}"}
        content = results[0].get("raw_content", "")
        if len(content) > 6000:
            content = content[:6000]
        return {"content": content, "url": url}
