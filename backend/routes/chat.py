import json
import logging

from flask import Blueprint, Response, current_app, request, stream_with_context

from backend.agent.agent import Agent, OnboardingAgent
from backend.config_manager import get_llm_config, get_onboarding_llm_config, get_integration_config
from backend.database import db
from backend.llm.factory import create_provider
from backend.models.chat import Conversation, Message

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("/conversations", methods=["GET"])
def list_conversations():
    convos = Conversation.query.order_by(Conversation.updated_at.desc()).all()
    return [c.to_dict() for c in convos]


@chat_bp.route("/conversations", methods=["POST"])
def create_conversation():
    data = request.get_json(silent=True) or {}
    convo = Conversation(title=data.get("title", "New Chat"))
    db.session.add(convo)
    db.session.commit()
    return convo.to_dict(), 201


@chat_bp.route("/conversations/<int:convo_id>", methods=["GET"])
def get_conversation(convo_id):
    convo = db.session.get(Conversation, convo_id)
    if not convo:
        return {"error": "Conversation not found"}, 404
    return convo.to_dict(include_messages=True)


@chat_bp.route("/conversations/<int:convo_id>", methods=["DELETE"])
def delete_conversation(convo_id):
    convo = db.session.get(Conversation, convo_id)
    if not convo:
        return {"error": "Conversation not found"}, 404
    db.session.delete(convo)
    db.session.commit()
    return "", 204


@chat_bp.route("/conversations/<int:convo_id>/messages", methods=["POST"])
def send_message(convo_id):
    convo = db.session.get(Conversation, convo_id)
    if not convo:
        return {"error": "Conversation not found"}, 404

    data = request.get_json()
    if not data or not data.get("content"):
        return {"error": "content is required"}, 400

    logger.info("Chat message received — conversation=%d content_len=%d",
                convo_id, len(data["content"]))

    # Save user message
    user_msg = Message(conversation_id=convo_id, role="user", content=data["content"])
    db.session.add(user_msg)
    db.session.commit()

    # Update conversation title from first message
    if len(convo.messages) == 1:
        convo.title = data["content"][:100]
        db.session.commit()

    # Build message history for LLM
    llm_messages = []
    for msg in convo.messages:
        llm_messages.append({"role": msg.role, "content": msg.content})

    # Get config dynamically from config manager (not Flask's static config)
    llm_config = get_llm_config()
    integration_config = get_integration_config()

    # Check if LLM is configured
    if not llm_config["api_key"] and llm_config["provider"] != "ollama":
        def error_stream():
            error_msg = {
                "event": "error",
                "data": json.dumps({
                    "message": "LLM is not configured. Please configure your API key in Settings (gear icon in the header)."
                })
            }
            yield f"event: {error_msg['event']}\ndata: {error_msg['data']}\n\n"

        return Response(
            stream_with_context(error_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Create provider and agent
    try:
        provider = create_provider(
            llm_config["provider"],
            llm_config["api_key"],
            llm_config["model"],
        )
    except Exception as e:
        logger.error(f"Failed to create LLM provider: {e}")
        error_message = f"Failed to initialize LLM provider: {str(e)}"
        def error_stream():
            error_msg = {
                "event": "error",
                "data": json.dumps({
                    "message": error_message
                })
            }
            yield f"event: {error_msg['event']}\ndata: {error_msg['data']}\n\n"

        return Response(
            stream_with_context(error_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    agent = Agent(
        provider,
        search_api_key=integration_config["search_api_key"],
        adzuna_app_id=integration_config["adzuna_app_id"],
        adzuna_app_key=integration_config["adzuna_app_key"],
        adzuna_country=integration_config["adzuna_country"],
        jsearch_api_key=integration_config["jsearch_api_key"],
    )

    def generate():
        full_text = ""
        tool_calls_log = []

        for event in agent.run(llm_messages):
            event_type = event["event"]
            event_data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {event_data}\n\n"

            if event_type == "text_delta":
                full_text += event["data"]["content"]
            elif event_type in ("tool_start", "tool_result", "tool_error"):
                tool_calls_log.append(event["data"])
            elif event_type == "done":
                # Save assistant message
                logger.info("Chat response complete — conversation=%d text_len=%d tool_calls=%d",
                            convo_id, len(full_text), len(tool_calls_log))
                with current_app.app_context():
                    assistant_msg = Message(
                        conversation_id=convo_id,
                        role="assistant",
                        content=full_text,
                        tool_calls=json.dumps(tool_calls_log) if tool_calls_log else None,
                    )
                    db.session.add(assistant_msg)
                    db.session.commit()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _get_onboarding_provider():
    """Build the LLM provider for onboarding, falling back to the main config.

    Raises ValueError if LLM is not configured.
    """
    # Get config dynamically from config manager (not Flask's static config)
    onboarding_config = get_onboarding_llm_config()
    provider_name = onboarding_config["provider"]
    api_key = onboarding_config["api_key"]
    model = onboarding_config["model"]

    if not api_key and provider_name != "ollama":
        raise ValueError("LLM is not configured. Please configure your API key in Settings.")

    return create_provider(provider_name, api_key, model)


@chat_bp.route("/onboarding/conversations", methods=["POST"])
def create_onboarding_conversation():
    convo = Conversation(title="Onboarding")
    db.session.add(convo)
    db.session.commit()
    return convo.to_dict(), 201


@chat_bp.route("/onboarding/conversations/<int:convo_id>/messages", methods=["POST"])
def send_onboarding_message(convo_id):
    convo = db.session.get(Conversation, convo_id)
    if not convo:
        return {"error": "Conversation not found"}, 404

    data = request.get_json()
    if not data or not data.get("content"):
        return {"error": "content is required"}, 400

    # Save user message
    user_msg = Message(conversation_id=convo_id, role="user", content=data["content"])
    db.session.add(user_msg)
    db.session.commit()

    # Build message history for LLM
    llm_messages = []
    for msg in convo.messages:
        llm_messages.append({"role": msg.role, "content": msg.content})

    try:
        provider = _get_onboarding_provider()
        agent = OnboardingAgent(provider)
    except Exception as e:
        logger.error(f"Failed to create onboarding provider: {e}")
        error_message = f"Failed to initialize LLM: {str(e)}"
        def error_stream():
            error_msg = {
                "event": "error",
                "data": json.dumps({
                    "message": error_message
                })
            }
            yield f"event: {error_msg['event']}\ndata: {error_msg['data']}\n\n"

        return Response(
            stream_with_context(error_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    logger.info("Onboarding message received — conversation=%d", convo_id)

    def generate():
        full_text = ""
        tool_calls_log = []

        for event in agent.run(llm_messages):
            event_type = event["event"]
            event_data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {event_data}\n\n"

            if event_type == "text_delta":
                full_text += event["data"]["content"]
            elif event_type in ("tool_start", "tool_result", "tool_error"):
                tool_calls_log.append(event["data"])
            elif event_type == "done":
                # Strip the onboarding marker from persisted text
                clean_text = full_text.replace("[ONBOARDING_COMPLETE]", "").rstrip()
                logger.info("Onboarding response complete — conversation=%d text_len=%d",
                            convo_id, len(clean_text))
                with current_app.app_context():
                    assistant_msg = Message(
                        conversation_id=convo_id,
                        role="assistant",
                        content=clean_text,
                        tool_calls=json.dumps(tool_calls_log) if tool_calls_log else None,
                    )
                    db.session.add(assistant_msg)
                    db.session.commit()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@chat_bp.route("/onboarding/kick", methods=["POST"])
def kick_onboarding():
    """Start the onboarding conversation with an initial assistant greeting.

    The frontend calls this once to get the agent's opening message without
    requiring the user to send a message first.
    """
    data = request.get_json(silent=True) or {}
    convo_id = data.get("conversation_id")
    if not convo_id:
        return {"error": "conversation_id is required"}, 400

    convo = db.session.get(Conversation, convo_id)
    if not convo:
        return {"error": "Conversation not found"}, 404

    # Inject a synthetic user message to trigger the agent's greeting.
    # LLM providers require at least one user message.
    kick_text = "Hi! I'm new here."
    kick_msg = Message(conversation_id=convo_id, role="user", content=kick_text)
    db.session.add(kick_msg)
    db.session.commit()
    llm_messages = [{"role": "user", "content": kick_text}]

    try:
        provider = _get_onboarding_provider()
        agent = OnboardingAgent(provider)
    except Exception as e:
        logger.error(f"Failed to create onboarding provider: {e}")
        error_message = f"Failed to initialize LLM: {str(e)}"
        def error_stream():
            error_msg = {
                "event": "error",
                "data": json.dumps({
                    "message": error_message
                })
            }
            yield f"event: {error_msg['event']}\ndata: {error_msg['data']}\n\n"

        return Response(
            stream_with_context(error_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    logger.info("Onboarding kick — conversation=%d", convo_id)

    def generate():
        full_text = ""
        tool_calls_log = []

        for event in agent.run(llm_messages):
            event_type = event["event"]
            event_data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {event_data}\n\n"

            if event_type == "text_delta":
                full_text += event["data"]["content"]
            elif event_type in ("tool_start", "tool_result", "tool_error"):
                tool_calls_log.append(event["data"])
            elif event_type == "done":
                clean_text = full_text.replace("[ONBOARDING_COMPLETE]", "").rstrip()
                logger.info("Onboarding kick complete — conversation=%d text_len=%d",
                            convo_id, len(clean_text))
                with current_app.app_context():
                    assistant_msg = Message(
                        conversation_id=convo_id,
                        role="assistant",
                        content=clean_text,
                        tool_calls=json.dumps(tool_calls_log) if tool_calls_log else None,
                    )
                    db.session.add(assistant_msg)
                    db.session.commit()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
