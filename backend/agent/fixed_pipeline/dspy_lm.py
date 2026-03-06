"""LangChain ↔ DSPy adapter.

Bridges DSPy's BaseLM interface to a LangChain BaseChatModel so that
DSPy modules (Predict, ChainOfThought, etc.) can use any LangChain-supported
LLM provider without going through LiteLLM.
"""

import logging
from dataclasses import dataclass, field

import dspy
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.agent.default.agent import _extract_text

logger = logging.getLogger(__name__)


# ── Minimal OpenAI-compatible response objects ─────────────────────────
# DSPy's _process_completion expects response.choices[i].message.content
# and response.usage with prompt_tokens / completion_tokens / total_tokens.


class _Usage(dict):
    """Dict-based usage object. DSPy's _process_lm_response calls
    ``dict(response.usage)`` which requires the object to be iterable.
    Using a dict subclass with attribute access satisfies both patterns."""

    def __init__(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        super().__init__(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens)

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


@dataclass
class _Message:
    content: str = ""
    role: str = "assistant"
    tool_calls: list = field(default_factory=list)


@dataclass
class _Choice:
    message: _Message = field(default_factory=_Message)
    index: int = 0
    finish_reason: str = "stop"


@dataclass
class _Response:
    choices: list[_Choice] = field(default_factory=list)
    usage: _Usage = field(default_factory=_Usage)
    model: str = ""


# ── Adapter ────────────────────────────────────────────────────────────


class LangChainLM(dspy.BaseLM):
    """DSPy BaseLM adapter that delegates to a LangChain BaseChatModel."""

    def __init__(self, langchain_model: BaseChatModel, **kwargs):
        # Use the model class name as the model identifier
        model_name = f"langchain:{type(langchain_model).__name__}"
        super().__init__(model=model_name, model_type="chat", **kwargs)
        self._lc_model = langchain_model

    def forward(self, prompt=None, messages=None, **kwargs):
        """Convert OpenAI-format messages to LangChain messages, invoke, return OpenAI-format response."""
        lc_messages = []

        if messages:
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))
        elif prompt:
            lc_messages.append(HumanMessage(content=prompt))
        else:
            lc_messages.append(HumanMessage(content=""))

        logger.debug("[LangChainLM] invoking with %d messages", len(lc_messages))

        response = self._lc_model.invoke(lc_messages)
        text = _extract_text(response.content)

        # Build usage from response metadata if available
        usage_meta = getattr(response, "usage_metadata", None) or {}
        if isinstance(usage_meta, dict):
            prompt_tokens = usage_meta.get("input_tokens", 0)
            completion_tokens = usage_meta.get("output_tokens", 0)
        else:
            prompt_tokens = getattr(usage_meta, "input_tokens", 0)
            completion_tokens = getattr(usage_meta, "output_tokens", 0)

        return _Response(
            choices=[_Choice(message=_Message(content=text))],
            usage=_Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model=self.model,
        )


def create_dspy_lm(langchain_model: BaseChatModel) -> LangChainLM:
    """Create a LangChainLM adapter from a LangChain model.

    Use the returned LM with ``dspy.context(lm=lm)`` as a context manager
    to set it for the current thread without mutating global state.
    """
    lm = LangChainLM(langchain_model)
    logger.info("Created DSPy LM adapter: %s", lm.model)
    return lm


# Keep old name around for backwards-compat but mark deprecated
configure_dspy = create_dspy_lm
