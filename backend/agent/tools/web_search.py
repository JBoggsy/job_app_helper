"""web_search and web_research tools — Tavily web search and research."""

from pydantic import BaseModel, Field
from tavily import TavilyClient

from ._registry import agent_tool


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    num_results: int = Field(default=5, description="Number of results (max 10)")


class WebResearchInput(BaseModel):
    query: str = Field(description="Research question or topic to investigate in depth")


class WebSearchMixin:
    @agent_tool(
        description=(
            "Search the web for current information. Returns an LLM-generated answer "
            "plus a list of relevant results with title, URL, content snippet, and "
            "relevance score. Use for simple-to-moderate queries. For complex topics "
            "requiring thorough, multi-angle investigation, use web_research instead."
        ),
        args_schema=WebSearchInput,
    )
    def web_search(self, query, num_results=5):
        if not self.search_api_key:
            return {"error": "No Tavily API key configured. Set SEARCH_API_KEY or configure it in Settings."}
        client = TavilyClient(api_key=self.search_api_key)
        response = client.search(
            query=query,
            max_results=min(num_results, 10),
            include_answer="advanced",
        )
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
            }
            for r in response.get("results", [])
        ]
        return {
            "answer": response.get("answer", ""),
            "results": results,
        }

    @agent_tool(
        description=(
            "Conduct in-depth web research on a complex topic. Uses Tavily's research "
            "agent to perform multi-step investigation and synthesize a comprehensive "
            "report with citations. Costs significantly more credits than web_search — "
            "only use for complex queries that require thorough, multi-angle research."
        ),
        args_schema=WebResearchInput,
    )
    def web_research(self, query):
        if not self.search_api_key:
            return {"error": "No Tavily API key configured. Set SEARCH_API_KEY or configure it in Settings."}
        client = TavilyClient(api_key=self.search_api_key)
        response = client.research(
            input=query,
            model="mini",
        )
        return {
            "report": response.get("response", ""),
            "sources": response.get("sources", []),
        }
