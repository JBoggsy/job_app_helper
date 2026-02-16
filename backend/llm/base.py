from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class StreamChunk:
    type: str  # "text", "tool_calls", "done", "error"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    @abstractmethod
    def stream_with_tools(self, messages, tools, system_prompt=""):
        """Yield StreamChunk objects from the LLM.

        Args:
            messages: list of {"role": str, "content": str | list} dicts
            tools: list of tool definition dicts (name, description, parameters)
            system_prompt: optional system prompt string

        Yields:
            StreamChunk with type "text", "tool_calls", "done", or "error"
        """
        ...
