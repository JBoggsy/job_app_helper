import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "..", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "")
    SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "")

    # Job search APIs
    ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
    ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")
    ADZUNA_COUNTRY = os.environ.get("ADZUNA_COUNTRY", "us")
    JSEARCH_API_KEY = os.environ.get("JSEARCH_API_KEY", "")

    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # Onboarding LLM — defaults to the main LLM provider when not set
    ONBOARDING_LLM_PROVIDER = os.environ.get("ONBOARDING_LLM_PROVIDER", "")
    ONBOARDING_LLM_API_KEY = os.environ.get("ONBOARDING_LLM_API_KEY", "")
    ONBOARDING_LLM_MODEL = os.environ.get("ONBOARDING_LLM_MODEL", "")
