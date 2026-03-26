"""
Configuration API routes.

Provides endpoints for reading and updating application configuration.
"""

from pathlib import Path

from flask import Blueprint, jsonify, request
from backend.config_manager import (
    load_config,
    save_config,
    config_to_dict,
    get_llm_config,
    get_integration_config
)
from backend.llm.llm_factory import create_llm_config, DEFAULT_MODELS
from backend.llm.model_listing import (
    list_models as _list_models,
    MODEL_LISTERS,
    is_ollama_running,
    pick_best_ollama_model,
)
import litellm
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

        if "search_llm" in data:
            if "search_llm" not in config:
                config["search_llm"] = {"provider": "", "api_key": "", "model": ""}
            for key, value in data["search_llm"].items():
                if value is not None and not is_masked_value(value):
                    config["search_llm"][key] = value

        if "integrations" in data:
            for key, value in data["integrations"].items():
                if value is not None and not is_masked_value(value):
                    config["integrations"][key] = value

        if "agent" in data:
            if "agent" not in config:
                config["agent"] = {"design": "default", "freeform_llm": {"provider": "", "api_key": "", "model": ""}, "orchestrated_llm": {"provider": "", "api_key": "", "model": ""}}
            agent_data = data["agent"]
            if "design" in agent_data and agent_data["design"] is not None:
                config["agent"]["design"] = agent_data["design"]
            for sub in ("freeform_llm", "orchestrated_llm"):
                if sub in agent_data:
                    if sub not in config["agent"]:
                        config["agent"][sub] = {"provider": "", "api_key": "", "model": ""}
                    for key, value in agent_data[sub].items():
                        if value is not None and not is_masked_value(value):
                            config["agent"][sub][key] = value

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

        # Try to create LLM config and make a test request
        try:
            llm_config = create_llm_config(provider, api_key, model)

            kwargs = {"model": llm_config.model}
            if llm_config.api_key:
                kwargs["api_key"] = llm_config.api_key
            if llm_config.api_base:
                kwargs["api_base"] = llm_config.api_base

            # Make a simple test request (non-streaming)
            response = litellm.completion(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond with just 'OK'."},
                    {"role": "user", "content": "Hello"},
                ],
                **kwargs,
            )
            test_response = response.choices[0].message.content

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
            error_type = "unknown"

            lower_msg = error_message.lower()

            # Provide more helpful error messages
            if "authentication" in lower_msg or "api key" in lower_msg:
                error_message = "Invalid API key"
                error_type = "auth_error"
            elif provider == "ollama" and ("not found" in lower_msg or "404" in lower_msg):
                # Ollama is reachable but the model isn't installed
                resolved_model = model or DEFAULT_MODELS.get("ollama")
                error_message = (
                    f"Ollama is running, but the model '{resolved_model}' "
                    f"was not found. Run `ollama pull {resolved_model}` or "
                    f"select an installed model from the dropdown below."
                )
                error_type = "model_not_found"
            elif provider == "ollama" and (
                "connection" in lower_msg
                or "connect" in lower_msg
                or "refused" in lower_msg
                or "unreachable" in lower_msg
            ):
                error_message = (
                    "Could not connect to Ollama. Make sure Ollama is "
                    "installed and running (check with `ollama list` in "
                    "your terminal)."
                )
                error_type = "connection_failed"
            elif "not found" in lower_msg:
                error_message = "Provider or model not found"
                error_type = "not_found"
            elif "rate limit" in lower_msg:
                error_message = "Rate limit exceeded"
                error_type = "rate_limit"
            elif provider == "ollama":
                # For any other Ollama error, check if server is reachable
                # to give a more targeted message
                if not is_ollama_running():
                    error_message = (
                        "Could not connect to Ollama. Make sure Ollama is "
                        "installed and running (check with `ollama list` in "
                        "your terminal)."
                    )
                    error_type = "connection_failed"

            return jsonify({
                "success": False,
                "error": error_message,
                "error_type": error_type,
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

        # If the key looks masked (contains asterisks), resolve the real key from config
        if api_key and '*' in api_key:
            config = load_config()
            # Check if this matches the main LLM provider or onboarding provider
            if config.get('llm', {}).get('provider') == provider_name:
                api_key = config.get('llm', {}).get('api_key', '')
            elif config.get('onboarding_llm', {}).get('provider') == provider_name:
                api_key = config.get('onboarding_llm', {}).get('api_key', '')
            elif config.get('search_llm', {}).get('provider') == provider_name:
                api_key = config.get('search_llm', {}).get('api_key', '')

        if not provider_name:
            return jsonify({"models": [], "error": "No provider specified"}), 200

        if provider_name not in MODEL_LISTERS:
            return jsonify({"models": [], "error": f"Unknown provider: {provider_name}"}), 200

        try:
            models = _list_models(provider_name, api_key=api_key)
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
    # Determine best available Ollama model dynamically
    ollama_default = pick_best_ollama_model() or DEFAULT_MODELS.get("ollama")

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
            "default_model": ollama_default,
            "requires_api_key": False
        }
    ]

    return jsonify(providers), 200


@config_bp.route('/api/telemetry/stats', methods=['GET'])
def telemetry_stats():
    """Get telemetry database summary statistics."""
    from backend.data_dir import get_data_dir
    from backend.telemetry.export import get_stats
    db_path = get_data_dir() / "telemetry.db"
    return jsonify(get_stats(db_path)), 200


@config_bp.route('/api/telemetry/export', methods=['GET'])
def telemetry_export():
    """Export the telemetry database.

    Query params:
        mode: "full" (default) or "anonymized"
    """
    import tempfile
    from flask import send_file

    from backend.data_dir import get_data_dir
    from backend.telemetry.export import export_anonymized, export_full

    db_path = get_data_dir() / "telemetry.db"
    if not db_path.exists():
        return jsonify({"error": "No telemetry data"}), 404

    mode = request.args.get("mode", "full")
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    output = Path(tmp.name)

    try:
        if mode == "anonymized":
            export_anonymized(db_path, output)
        else:
            export_full(db_path, output)

        return send_file(
            str(output),
            mimetype="application/x-sqlite3",
            as_attachment=True,
            download_name=f"shortlist_telemetry_{mode}.db",
        )
    except Exception as e:
        logger.error("Telemetry export failed: %s", e)
        return jsonify({"error": str(e)}), 500


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
    job_search_configured = bool(integration_config.get('rapidapi_key'))

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
