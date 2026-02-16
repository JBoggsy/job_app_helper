import json

import anthropic

from backend.llm.base import LLMProvider, StreamChunk, ToolCall


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key, model="claude-sonnet-4-5-20250929"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def _convert_tools(self, tools):
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]

    def stream_with_tools(self, messages, tools, system_prompt=""):
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": messages,
                "tools": self._convert_tools(tools),
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            with self.client.messages.stream(**kwargs) as stream:
                current_text = ""
                tool_calls = []
                current_tool = None
                current_tool_json = ""

                for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            current_text = ""
                        elif event.content_block.type == "tool_use":
                            current_tool = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                            }
                            current_tool_json = ""

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            current_text += event.delta.text
                            yield StreamChunk(type="text", content=event.delta.text)
                        elif event.delta.type == "input_json_delta":
                            current_tool_json += event.delta.partial_json

                    elif event.type == "content_block_stop":
                        if current_tool:
                            args = json.loads(current_tool_json) if current_tool_json else {}
                            tool_calls.append(
                                ToolCall(
                                    id=current_tool["id"],
                                    name=current_tool["name"],
                                    arguments=args,
                                )
                            )
                            current_tool = None
                            current_tool_json = ""

                    elif event.type == "message_stop":
                        pass

                if tool_calls:
                    yield StreamChunk(type="tool_calls", tool_calls=tool_calls)

                yield StreamChunk(type="done")

        except Exception as e:
            yield StreamChunk(type="error", content=str(e))
