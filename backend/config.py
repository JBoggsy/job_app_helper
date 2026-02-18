import os
from backend.config_manager import get_config_value, get_onboarding_llm_config
from backend.data_dir import get_data_dir


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(get_data_dir() / "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    # LLM configuration - uses config file with env var override
    LLM_PROVIDER = get_config_value("llm.provider", "anthropic")
    LLM_API_KEY = get_config_value("llm.api_key", "")
    LLM_MODEL = get_config_value("llm.model", "")

    # Search API
    SEARCH_API_KEY = get_config_value("integrations.search_api_key", "")

    # Job search APIs
    ADZUNA_APP_ID = get_config_value("integrations.adzuna_app_id", "")
    ADZUNA_APP_KEY = get_config_value("integrations.adzuna_app_key", "")
    ADZUNA_COUNTRY = get_config_value("integrations.adzuna_country", "us")
    JSEARCH_API_KEY = get_config_value("integrations.jsearch_api_key", "")

    # Logging
    LOG_LEVEL = get_config_value("logging.level", "INFO")

    # Onboarding LLM — defaults to the main LLM provider when not set
    _onboarding_config = get_onboarding_llm_config()
    ONBOARDING_LLM_PROVIDER = _onboarding_config["provider"] or LLM_PROVIDER
    ONBOARDING_LLM_API_KEY = _onboarding_config["api_key"] or LLM_API_KEY
    ONBOARDING_LLM_MODEL = _onboarding_config["model"] or LLM_MODEL
