"""
Configuration file management for Shortlist.

Provides functions to read and write configuration to config.json,
with fallback to environment variables.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

from backend.data_dir import get_data_dir


def _config_file() -> Path:
    """Return path to config.json (lazy to respect DATA_DIR set after import)."""
    return get_data_dir() / 'config.json'

# Default configuration template
DEFAULT_CONFIG = {
    "llm": {
        "provider": "anthropic",
        "api_key": "",
        "model": ""
    },
    "onboarding_llm": {
        "provider": "",
        "api_key": "",
        "model": ""
    },
    "search_llm": {
        "provider": "",
        "api_key": "",
        "model": ""
    },
    "agent": {
        "design": "default",
        "freeform_llm": {
            "provider": "",
            "api_key": "",
            "model": ""
        },
        "orchestrated_llm": {
            "provider": "",
            "api_key": "",
            "model": ""
        }
    },
    "integrations": {
        "search_api_key": "",
        "rapidapi_key": ""
    },
    "logging": {
        "level": "INFO"
    },
    "telemetry": {
        "enabled": True,
        "retention_days": 90
    }
}


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json.
    Creates file with defaults if it doesn't exist.

    Returns:
        Dictionary with configuration settings
    """
    if not _config_file().exists():
        logger.info(f"Config file not found at {_config_file()}, creating with defaults")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(_config_file(), 'r') as f:
            config = json.load(f)
            logger.info("Configuration loaded from file")
            return config
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing config.json: {e}")
        logger.info("Falling back to default configuration")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        logger.error(f"Error loading config.json: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """
    Save configuration to config.json.

    Args:
        config: Configuration dictionary to save

    Returns:
        True if save was successful, False otherwise
    """
    try:
        with open(_config_file(), 'w') as f:
            json.dump(config, f, indent=2)
            logger.info("Configuration saved to file")
        return True
    except Exception as e:
        logger.error(f"Error saving config.json: {e}")
        return False


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Get a configuration value by dot-separated path.
    Checks environment variables first, then config file.

    Args:
        key_path: Dot-separated path (e.g., "llm.provider")
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    # Check environment variable first (convert dot.path to UPPER_SNAKE_CASE)
    env_key = key_path.upper().replace('.', '_')
    env_value = os.getenv(env_key)
    if env_value is not None:
        return env_value

    # Fall back to config file
    config = load_config()
    keys = key_path.split('.')
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value if value != "" else default


def update_config_value(key_path: str, value: Any) -> bool:
    """
    Update a configuration value by dot-separated path.

    Args:
        key_path: Dot-separated path (e.g., "llm.provider")
        value: New value to set

    Returns:
        True if update was successful, False otherwise
    """
    config = load_config()
    keys = key_path.split('.')

    # Navigate to the nested dictionary
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Set the value
    current[keys[-1]] = value

    return save_config(config)


def get_llm_config() -> Dict[str, Optional[str]]:
    """
    Get LLM configuration with environment variable fallback.

    Returns:
        Dictionary with provider, api_key, and model
    """
    return {
        "provider": get_config_value("llm.provider", "anthropic"),
        "api_key": get_config_value("llm.api_key"),
        "model": get_config_value("llm.model")
    }


def get_onboarding_llm_config() -> Dict[str, Optional[str]]:
    """
    Get onboarding LLM configuration with fallback to main LLM config.

    Returns:
        Dictionary with provider, api_key, and model
    """
    main_config = get_llm_config()

    return {
        "provider": get_config_value("onboarding_llm.provider", main_config["provider"]),
        "api_key": get_config_value("onboarding_llm.api_key", main_config["api_key"]),
        "model": get_config_value("onboarding_llm.model", main_config["model"])
    }


def get_search_llm_config() -> Dict[str, Optional[str]]:
    """
    Get search sub-agent LLM configuration with fallback to main LLM config.

    Returns:
        Dictionary with provider, api_key, and model
    """
    main_config = get_llm_config()

    return {
        "provider": get_config_value("search_llm.provider", main_config["provider"]),
        "api_key": get_config_value("search_llm.api_key", main_config["api_key"]),
        "model": get_config_value("search_llm.model", main_config["model"])
    }


def get_active_mode_llm_config() -> Dict[str, Optional[str]]:
    """Get LLM configuration for the currently active agent mode.

    Checks the per-mode override (``agent.freeform_llm`` or
    ``agent.orchestrated_llm``) first, then falls back to the main ``llm``
    config for any empty fields.
    """
    from backend.agent import DESIGN_MODES

    design = get_config_value("agent.design", "default") or "default"
    mode = DESIGN_MODES.get(design, design)  # "freeform" or "orchestrated"

    main_config = get_llm_config()

    prefix = f"agent.{mode}_llm"
    return {
        "provider": get_config_value(f"{prefix}.provider", main_config["provider"]),
        "api_key": get_config_value(f"{prefix}.api_key", main_config["api_key"]),
        "model": get_config_value(f"{prefix}.model", main_config["model"]),
    }


def get_integration_config() -> Dict[str, Optional[str]]:
    """
    Get integration API keys (search, job boards, etc.).

    Returns:
        Dictionary with all integration API keys
    """
    # Support legacy jsearch_api_key field as fallback for rapidapi_key
    rapidapi_key = (
        get_config_value("integrations.rapidapi_key")
        or get_config_value("integrations.jsearch_api_key")
    )
    return {
        "search_api_key": get_config_value("integrations.search_api_key"),
        "rapidapi_key": rapidapi_key,
    }


def config_to_dict() -> Dict[str, Any]:
    """
    Get the full configuration as a dictionary.
    Masks sensitive values (API keys) with asterisks.

    Returns:
        Configuration dictionary with masked sensitive values
    """
    config = load_config()

    # Create a deep copy and mask sensitive values
    masked_config = json.loads(json.dumps(config))

    def mask_value(value: str) -> str:
        """Mask API key/sensitive value"""
        if not value or len(value) < 8:
            return ""
        return value[:4] + "*" * (len(value) - 8) + value[-4:]

    # Mask API keys
    if "llm" in masked_config and "api_key" in masked_config["llm"]:
        masked_config["llm"]["api_key"] = mask_value(masked_config["llm"]["api_key"])

    if "onboarding_llm" in masked_config and "api_key" in masked_config["onboarding_llm"]:
        masked_config["onboarding_llm"]["api_key"] = mask_value(masked_config["onboarding_llm"]["api_key"])

    if "search_llm" in masked_config and "api_key" in masked_config["search_llm"]:
        masked_config["search_llm"]["api_key"] = mask_value(masked_config["search_llm"]["api_key"])

    # Mask per-mode LLM API keys
    if "agent" in masked_config:
        for sub in ("freeform_llm", "orchestrated_llm"):
            if sub in masked_config["agent"] and "api_key" in masked_config["agent"][sub]:
                masked_config["agent"][sub]["api_key"] = mask_value(masked_config["agent"][sub]["api_key"])

    if "integrations" in masked_config:
        for key in ["search_api_key", "rapidapi_key", "jsearch_api_key"]:
            if key in masked_config["integrations"]:
                masked_config["integrations"][key] = mask_value(masked_config["integrations"][key])

    return masked_config
