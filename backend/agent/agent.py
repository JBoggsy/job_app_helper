import json

from backend.llm.base import LLMProvider
from backend.agent.tools import TOOL_DEFINITIONS, AgentTools

SYSTEM_PROMPT = """You are a helpful job search assistant. You help users find, research, and track job applications.

You have access to tools that let you:
- Search the web for job postings
- Scrape job posting URLs to extract details
- Add jobs to the user's tracker
- List jobs already being tracked

When the user asks you to find jobs, search for them, extract the relevant details (company, title, location, salary, remote type, etc.), and offer to add them to the tracker. When scraping a URL, extract as much structured information as possible.

Be concise and helpful. After adding jobs, confirm what was added."""

MAX_ITERATIONS = 10


class Agent:
    def __init__(self, provider: LLMProvider, search_api_key=""):
        self.provider = provider
        self.tools = AgentTools(search_api_key=search_api_key)

    def run(self, messages):
        """Run the agent loop, yielding SSE event dicts.

        Yields dicts with 'event' and 'data' keys:
            - text_delta: {"content": "..."}
            - tool_start: {"id": "...", "name": "...", "arguments": {...}}
            - tool_result: {"id": "...", "name": "...", "result": {...}}
            - tool_error: {"id": "...", "name": "...", "error": "..."}
            - done: {"content": "full accumulated text"}
            - error: {"message": "..."}
        """
        working_messages = [dict(m) for m in messages]
        full_text = ""

        for _ in range(MAX_ITERATIONS):
            text_accum = ""
            tool_calls = []

            for chunk in self.provider.stream_with_tools(
                working_messages, TOOL_DEFINITIONS, SYSTEM_PROMPT
            ):
                if chunk.type == "text":
                    text_accum += chunk.content
                    full_text += chunk.content
                    yield {"event": "text_delta", "data": {"content": chunk.content}}

                elif chunk.type == "tool_calls":
                    tool_calls = chunk.tool_calls

                elif chunk.type == "error":
                    yield {"event": "error", "data": {"message": chunk.content}}
                    return

            if not tool_calls:
                yield {"event": "done", "data": {"content": full_text}}
                return

            # Build assistant message content blocks
            content_blocks = []
            if text_accum:
                content_blocks.append({"type": "text", "text": text_accum})
            for tc in tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                })
            working_messages.append({"role": "assistant", "content": content_blocks})

            # Execute tools and collect results
            tool_result_blocks = []
            for tc in tool_calls:
                yield {
                    "event": "tool_start",
                    "data": {"id": tc.id, "name": tc.name, "arguments": tc.arguments},
                }
                result = self.tools.execute(tc.name, tc.arguments)
                if "error" in result:
                    yield {
                        "event": "tool_error",
                        "data": {"id": tc.id, "name": tc.name, "error": result["error"]},
                    }
                else:
                    yield {
                        "event": "tool_result",
                        "data": {"id": tc.id, "name": tc.name, "result": result},
                    }
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": json.dumps(result),
                })

            working_messages.append({"role": "user", "content": tool_result_blocks})

        yield {"event": "error", "data": {"message": "Max iterations reached"}}
