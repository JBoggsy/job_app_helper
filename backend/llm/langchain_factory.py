"""LangChain ChatModel factory.

Creates a LangChain BaseChatModel instance for a given provider name,
API key, and optional model override. This replaces the old
create_provider() factory that returned custom LLMProvider instances.
"""

import logging

from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

# Default models per provider (matching previous custom provider defaults)
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5-20250929",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.1",
}


def create_langchain_model(
    provider_name: str, api_key: str, model: str = ""
) -> BaseChatModel:
    """Create a LangChain ChatModel for the given provider.

    Args:
        provider_name: One of "anthropic", "openai", "gemini", "ollama"
        api_key: API key for the provider (ignored for Ollama)
        model: Optional model override; each provider has a sensible default

    Returns:
        A BaseChatModel instance (ChatAnthropic, ChatOpenAI, etc.)

    Raises:
        ValueError: If provider_name is not recognized
    """
    resolved_model = model or DEFAULT_MODELS.get(provider_name, "")

    if provider_name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model=resolved_model,
            api_key=api_key,
            max_tokens=4096,
        )

    elif provider_name == "openai":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
        )

    elif provider_name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=resolved_model,
            google_api_key=api_key,
        )

    elif provider_name == "ollama":
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=resolved_model,
            base_url="http://localhost:11434",
        )

    else:
        available = list(DEFAULT_MODELS.keys())
        raise ValueError(
            f"Unknown LLM provider: {provider_name}. Available: {available}"
        )

    logger.info(
        "Created LangChain model: %s (model=%s)",
        provider_name,
        resolved_model,
    )
    return llm
