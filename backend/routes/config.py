"""
Configuration API routes.

Provides endpoints for reading and updating application configuration.
"""

from flask import Blueprint, jsonify, request
from backend.config_manager import (
    load_config,
    save_config,
    config_to_dict,
    update_config_value,
    get_llm_config,
    get_integration_config
)
from backend.llm.factory import create_provider, PROVIDERS
import logging

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    """
    Get current configuration (with masked API keys).

    Returns:
        JSON response with configuration
    """
    try:
        config = config_to_dict()
        return jsonify(config), 200
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"error": "Failed to load configuration"}), 500


@config_bp.route('/api/config', methods=['POST'])
def update_config():
    """
    Update configuration.

    Request body should contain the full or partial configuration to update.

    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        def is_masked_value(value):
            """Check if a value appears to be masked (contains asterisks)"""
            return isinstance(value, str) and "*" in value

        # Load current config
        config = load_config()

        # Update config with provided data
        if "llm" in data:
            for key, value in data["llm"].items():
                # Only update if value is provided and not masked
                if value is not None and not is_masked_value(value):
                    config["llm"][key] = value

        if "onboarding_llm" in data:
            for key, value in data["onboarding_llm"].items():
                if value is not None and not is_masked_value(value):
                    config["onboarding_llm"][key] = value

        if "integrations" in data:
            for key, value in data["integrations"].items():
                if value is not None and not is_masked_value(value):
                    config["integrations"][key] = value

        if "logging" in data:
            for key, value in data["logging"].items():
                if value is not None and not is_masked_value(value):
                    config["logging"][key] = value

        # Save updated config
        if save_config(config):
            logger.info("Configuration updated successfully")
            return jsonify({"success": True, "message": "Configuration updated"}), 200
        else:
            return jsonify({"error": "Failed to save configuration"}), 500

    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"error": str(e)}), 500


@config_bp.route('/api/config/test', methods=['POST'])
def test_connection():
    """
    Test LLM provider connection with provided or current credentials.

    Request body can optionally contain:
    - provider: LLM provider to test
    - api_key: API key to test
    - model: Model to test (optional)

    Returns:
        JSON response with test result
    """
    try:
        data = request.get_json() or {}

        # Use provided credentials or fall back to current config
        llm_config = get_llm_config()
        provider = data.get('provider', llm_config['provider'])
        api_key = data.get('api_key', llm_config['api_key'])
        model = data.get('model', llm_config['model'])

        if not provider:
            return jsonify({"success": False, "error": "No provider specified"}), 400

        if not api_key and provider != 'ollama':
            return jsonify({"success": False, "error": "No API key provided"}), 400

        # Try to create provider and make a test request
        try:
            llm_provider = create_provider(provider, api_key, model)

            # Make a simple test request
            test_messages = [{"role": "user", "content": "Hello"}]
            test_response = ""

            for chunk in llm_provider.stream_with_tools(
                system_prompt="You are a helpful assistant. Respond with just 'OK'.",
                messages=test_messages,
                tools=[]
            ):
                if chunk.content:
                    test_response += chunk.content

            if test_response:
                logger.info(f"LLM connection test successful for provider: {provider}")
                return jsonify({
                    "success": True,
                    "message": f"Successfully connected to {provider}",
                    "provider": provider
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "No response from provider"
                }), 500

        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            error_message = str(e)

            # Provide more helpful error messages
            if "authentication" in error_message.lower() or "api key" in error_message.lower():
                error_message = "Invalid API key"
            elif "not found" in error_message.lower():
                error_message = "Provider or model not found"
            elif "rate limit" in error_message.lower():
                error_message = "Rate limit exceeded"

            return jsonify({
                "success": False,
                "error": error_message
            }), 400

    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@config_bp.route('/api/config/models', methods=['POST'])
def list_models():
    """
    List available models for a given provider.

    Request body:
    - provider: LLM provider name
    - api_key: API key (optional for ollama)

    Returns:
        JSON response with models list (always HTTP 200 for graceful fallback)
    """
    try:
        data = request.get_json() or {}
        provider_name = data.get('provider')
        api_key = data.get('api_key', '')

        if not provider_name:
            return jsonify({"models": [], "error": "No provider specified"}), 200

        provider_cls = PROVIDERS.get(provider_name)
        if not provider_cls:
            return jsonify({"models": [], "error": f"Unknown provider: {provider_name}"}), 200

        try:
            models = provider_cls.list_models(api_key=api_key)
            return jsonify({"models": models}), 200
        except Exception as e:
            logger.warning("Failed to list models for %s: %s", provider_name, e)
            return jsonify({"models": [], "error": str(e)}), 200

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return jsonify({"models": [], "error": str(e)}), 200


@config_bp.route('/api/config/providers', methods=['GET'])
def get_providers():
    """
    Get list of available LLM providers with their default models.

    Returns:
        JSON response with provider information
    """
    providers = [
        {
            "id": "anthropic",
            "name": "Anthropic Claude",
            "default_model": "claude-sonnet-4-5-20250929",
            "requires_api_key": True
        },
        {
            "id": "openai",
            "name": "OpenAI GPT",
            "default_model": "gpt-4o",
            "requires_api_key": True
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "default_model": "gemini-2.0-flash",
            "requires_api_key": True
        },
        {
            "id": "ollama",
            "name": "Ollama (Local)",
            "default_model": "llama3.1",
            "requires_api_key": False
        }
    ]

    return jsonify(providers), 200


@config_bp.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.

    Checks if the application is configured and ready to use.

    Returns:
        JSON response with health status
    """
    llm_config = get_llm_config()
    integration_config = get_integration_config()

    # Check if LLM is configured
    llm_configured = bool(llm_config.get('api_key')) or llm_config.get('provider') == 'ollama'

    # Check optional integrations
    search_configured = bool(integration_config.get('search_api_key'))
    job_search_configured = bool(
        integration_config.get('jsearch_api_key') or
        (integration_config.get('adzuna_app_id') and integration_config.get('adzuna_app_key'))
    )

    health_status = {
        "status": "healthy" if llm_configured else "needs_configuration",
        "llm": {
            "configured": llm_configured,
            "provider": llm_config.get('provider', 'none'),
            "message": "LLM is configured" if llm_configured else "Please configure your LLM API key in Settings"
        },
        "integrations": {
            "search": {
                "configured": search_configured,
                "message": "Web search enabled" if search_configured else "Web search disabled (optional)"
            },
            "job_search": {
                "configured": job_search_configured,
                "message": "Job search enabled" if job_search_configured else "Job board search disabled (optional)"
            }
        }
    }

    status_code = 200 if llm_configured else 503
    return jsonify(health_status), status_code
