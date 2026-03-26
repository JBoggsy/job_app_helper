"""Model listing functions for each LLM provider.

These use the raw SDKs directly (not LiteLLM) to list available models
from each provider's API.  The ``/api/config/models`` endpoint uses these
to enumerate models without depending on the agent code.
"""

import logging

import requests

logger = logging.getLogger(__name__)


def list_anthropic_models(api_key: str = "", **kwargs) -> list[dict]:
    """List available Anthropic models.

    Returns:
        List of dicts with ``id`` and ``name`` keys.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    models = []
    for model in client.models.list():
        models.append({"id": model.id, "name": getattr(model, "display_name", model.id)})
    models.sort(key=lambda m: m["id"])
    return models


def list_openai_models(api_key: str = "", **kwargs) -> list[dict]:
    """List available OpenAI chat models.

    Returns:
        List of dicts with ``id`` keys.
    """
    import openai

    client = openai.OpenAI(api_key=api_key)
    chat_prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt")
    models = []
    for model in client.models.list():
        if model.id.startswith(chat_prefixes):
            models.append({"id": model.id})
    models.sort(key=lambda m: m["id"])
    return models


def list_gemini_models(api_key: str = "", **kwargs) -> list[dict]:
    """List available Google Gemini models that support content generation.

    Returns:
        List of dicts with ``id`` and ``name`` keys.
    """
    from google import genai

    client = genai.Client(api_key=api_key)
    models = []
    for model in client.models.list():
        supported = [
            a.value if hasattr(a, "value") else str(a)
            for a in (model.supported_actions or [])
        ]
        if "generateContent" not in supported:
            continue
        model_id = model.name
        if model_id.startswith("models/"):
            model_id = model_id[len("models/"):]
        models.append({"id": model_id, "name": model.display_name or model_id})
    models.sort(key=lambda m: m["id"])
    return models


def list_ollama_models(api_key: str = "", **kwargs) -> list[dict]:
    """List locally available Ollama models.

    Args:
        api_key: Unused (included for uniform signature).
        **kwargs: Optional ``base_url`` (defaults to ``http://localhost:11434``).

    Returns:
        List of dicts with ``id`` keys.
    """
    base_url = kwargs.get("base_url", "http://localhost:11434").rstrip("/")
    resp = requests.get(f"{base_url}/api/tags", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    models = []
    for m in data.get("models", []):
        models.append({"id": m["name"]})
    models.sort(key=lambda m: m["id"])
    return models


def is_ollama_running(base_url: str = "http://localhost:11434") -> bool:
    """Check whether the Ollama server is reachable.

    Args:
        base_url: Ollama server URL.

    Returns:
        ``True`` if the server responds, ``False`` otherwise.
    """
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        return resp.ok
    except Exception:
        return False


# Ranked list of known high-quality Ollama models, in descending preference.
# Entries are matched as prefixes against the model id (before the ":" tag).
_PREFERRED_OLLAMA_MODELS = [
    "llama3.3",
    "llama3.1",
    "llama3.2",
    "qwen3",
    "qwen2.5",
    "gemma3",
    "deepseek-r1",
    "mistral",
    "phi4",
    "command-r",
]


def _parse_model_size(model_id: str) -> float | None:
    """Try to extract a numeric parameter size (in billions) from a model tag.

    For example ``"qwen3.5:35b"`` → ``35.0``, ``"llama3.1:8b-instruct"`` →
    ``8.0``.  Returns ``None`` if no size is found.
    """
    import re

    tag = model_id.split(":")[-1] if ":" in model_id else ""
    match = re.search(r"(\d+(?:\.\d+)?)b", tag, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def pick_best_ollama_model(base_url: str = "http://localhost:11434") -> str | None:
    """Query Ollama for installed models and pick the best one.

    Selection strategy:
    1. Match against :pydata:`_PREFERRED_OLLAMA_MODELS` (preference order).
       Within a preference tier, prefer larger parameter sizes.
    2. If no preferred model matches, pick the model with the largest
       detectable parameter size.
    3. Fall back to the first model alphabetically.

    Returns:
        Model id string, or ``None`` if Ollama is unreachable / has no models.
    """
    try:
        models = list_ollama_models(base_url=base_url)
    except Exception:
        return None

    if not models:
        return None

    ids = [m["id"] for m in models]

    # Try preferred models in order
    for pref in _PREFERRED_OLLAMA_MODELS:
        candidates = [mid for mid in ids if mid.split(":")[0] == pref]
        if candidates:
            # Among candidates, prefer larger size
            candidates.sort(key=lambda m: _parse_model_size(m) or 0, reverse=True)
            return candidates[0]

    # No preferred model found — pick largest by parameter size
    sized = [(mid, _parse_model_size(mid)) for mid in ids]
    sized_only = [(mid, s) for mid, s in sized if s is not None]
    if sized_only:
        sized_only.sort(key=lambda t: t[1], reverse=True)
        return sized_only[0][0]

    # Fall back to first alphabetically
    ids.sort()
    return ids[0]


# Registry mapping provider names to their listing functions.
MODEL_LISTERS: dict[str, callable] = {
    "anthropic": list_anthropic_models,
    "openai": list_openai_models,
    "gemini": list_gemini_models,
    "ollama": list_ollama_models,
}


def list_models(provider_name: str, api_key: str = "", **kwargs) -> list[dict]:
    """List available models for a provider.

    Args:
        provider_name: One of ``anthropic``, ``openai``, ``gemini``, ``ollama``.
        api_key: API key (not needed for Ollama).
        **kwargs: Extra options forwarded to the provider-specific lister.

    Returns:
        List of dicts with at least an ``id`` key.

    Raises:
        ValueError: If *provider_name* is not recognised.
    """
    lister = MODEL_LISTERS.get(provider_name)
    if not lister:
        raise ValueError(f"Unknown provider: {provider_name}")
    return lister(api_key=api_key, **kwargs)
