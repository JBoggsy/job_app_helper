from backend.llm.anthropic_provider import AnthropicProvider

PROVIDERS = {
    "anthropic": AnthropicProvider,
}


def create_provider(name, api_key, model=None):
    """Create an LLM provider instance.

    Args:
        name: provider name (e.g. "anthropic", "openai")
        api_key: API key for the provider
        model: optional model override

    Returns:
        LLMProvider instance
    """
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown LLM provider: {name}. Available: {list(PROVIDERS)}")

    kwargs = {"api_key": api_key}
    if model:
        kwargs["model"] = model
    return cls(**kwargs)
