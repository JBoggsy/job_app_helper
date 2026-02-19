import json
import logging
import uuid

import requests

from backend.llm.base import LLMProvider, StreamChunk, ToolCall

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, api_key="", model="llama3.1", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _convert_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

    def stream_with_tools(self, messages, tools, system_prompt=""):
        try:
            api_messages = []
            if system_prompt:
                api_messages.append({"role": "system", "content": system_prompt})

            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Flatten content blocks to text
                    parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block["text"])
                            elif block.get("type") == "tool_result":
                                parts.append(block["content"])
                    api_messages.append({"role": msg["role"], "content": "\n".join(parts)})
                else:
                    api_messages.append({"role": msg["role"], "content": content})

            logger.info("Ollama streaming request — model=%s messages=%d tools=%d",
                        self.model, len(api_messages), len(tools))

            resp = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": api_messages,
                    "tools": self._convert_tools(tools),
                    "stream": True,
                },
                stream=True,
                timeout=120,
            )
            resp.raise_for_status()

            tool_calls = []

            for line in resp.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                msg = data.get("message", {})

                if msg.get("content"):
                    yield StreamChunk(type="text", content=msg["content"])

                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn = tc.get("function", {})
                        tool_calls.append(
                            ToolCall(
                                id=str(uuid.uuid4()),
                                name=fn.get("name", ""),
                                arguments=fn.get("arguments", {}),
                            )
                        )

                if data.get("done"):
                    break

            if tool_calls:
                logger.info("Ollama response — %d tool call(s): %s",
                            len(tool_calls),
                            ", ".join(tc.name for tc in tool_calls))
                yield StreamChunk(type="tool_calls", tool_calls=tool_calls)
            else:
                logger.info("Ollama response — text only")

            yield StreamChunk(type="done")

        except Exception as e:
            logger.exception("Ollama streaming error")
            yield StreamChunk(type="error", content=str(e))

    @staticmethod
    def list_models(api_key="", **kwargs):
        base_url = kwargs.get("base_url", "http://localhost:11434").rstrip("/")
        resp = requests.get(f"{base_url}/api/tags", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        models = []
        for m in data.get("models", []):
            models.append({"id": m["name"]})
        models.sort(key=lambda m: m["id"])
        return models
