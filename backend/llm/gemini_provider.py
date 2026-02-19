import logging
import uuid

from google import genai
from google.genai import types

from backend.llm.base import LLMProvider, StreamChunk, ToolCall

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    def __init__(self, api_key, model="gemini-2.0-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model

    def _convert_tools(self, tools):
        """Convert tool definitions to google.genai FunctionDeclaration format."""
        declarations = []
        for t in tools:
            params = dict(t["parameters"])
            # Gemini doesn't accept "additionalProperties" or empty required
            params.pop("additionalProperties", None)
            if not params.get("required"):
                params.pop("required", None)
            declarations.append(types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=params,
            ))
        return declarations

    def _build_contents(self, messages):
        """Convert messages to google.genai Content format."""
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg.get("content", "")
            if isinstance(content, str):
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=content)],
                ))
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if block.get("type") == "text":
                        parts.append(types.Part.from_text(text=block["text"]))
                    elif block.get("type") == "tool_use":
                        parts.append(types.Part.from_function_call(
                            name=block["name"],
                            args=block["input"],
                        ))
                    elif block.get("type") == "tool_result":
                        parts.append(types.Part.from_function_response(
                            name="tool",
                            response={"result": block["content"]},
                        ))
                if parts:
                    contents.append(types.Content(role=role, parts=parts))
        return contents

    def stream_with_tools(self, messages, tools, system_prompt=""):
        try:
            tool_declarations = self._convert_tools(tools)
            contents = self._build_contents(messages)

            config = types.GenerateContentConfig(
                system_instruction=system_prompt or None,
                tools=[types.Tool(function_declarations=tool_declarations)],
            )

            logger.info("Gemini streaming request — model=%s messages=%d tools=%d",
                        self.model_name, len(contents), len(tool_declarations))

            tool_calls = []
            for chunk in self.client.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config,
            ):
                if not chunk.candidates:
                    continue
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        yield StreamChunk(type="text", content=part.text)
                    elif part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        tool_calls.append(
                            ToolCall(id=str(uuid.uuid4()), name=fc.name, arguments=args)
                        )

            if tool_calls:
                logger.info("Gemini response — %d tool call(s): %s",
                            len(tool_calls),
                            ", ".join(tc.name for tc in tool_calls))
                yield StreamChunk(type="tool_calls", tool_calls=tool_calls)
            else:
                logger.info("Gemini response — text only")

            yield StreamChunk(type="done")

        except Exception as e:
            logger.exception("Gemini streaming error")
            yield StreamChunk(type="error", content=str(e))

    @staticmethod
    def list_models(api_key="", **kwargs):
        client = genai.Client(api_key=api_key)
        models = []
        for model in client.models.list():
            supported = [a.value if hasattr(a, 'value') else str(a)
                         for a in (model.supported_actions or [])]
            if "generateContent" not in supported:
                continue
            model_id = model.name
            if model_id.startswith("models/"):
                model_id = model_id[len("models/"):]
            models.append({"id": model_id, "name": model.display_name or model_id})
        models.sort(key=lambda m: m["id"])
        return models
