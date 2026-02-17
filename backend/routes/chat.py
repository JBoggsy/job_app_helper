import json

from flask import Blueprint, Response, current_app, request, stream_with_context

from backend.agent.agent import Agent, OnboardingAgent
from backend.database import db
from backend.llm.factory import create_provider
from backend.models.chat import Conversation, Message

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

    # Create provider and agent
    config = current_app.config
    provider = create_provider(
        config["LLM_PROVIDER"],
        config["LLM_API_KEY"],
        config["LLM_MODEL"] or None,
    )
    agent = Agent(
        provider,
        search_api_key=config["SEARCH_API_KEY"],
        adzuna_app_id=config["ADZUNA_APP_ID"],
        adzuna_app_key=config["ADZUNA_APP_KEY"],
        adzuna_country=config["ADZUNA_COUNTRY"],
        jsearch_api_key=config["JSEARCH_API_KEY"],
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


def _get_onboarding_provider(config):
    """Build the LLM provider for onboarding, falling back to the main config."""
    provider_name = config["ONBOARDING_LLM_PROVIDER"] or config["LLM_PROVIDER"]
    api_key = config["ONBOARDING_LLM_API_KEY"] or config["LLM_API_KEY"]
    model = config["ONBOARDING_LLM_MODEL"] or config["LLM_MODEL"] or None
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

    config = current_app.config
    provider = _get_onboarding_provider(config)
    agent = OnboardingAgent(provider)

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

    config = current_app.config
    provider = _get_onboarding_provider(config)
    agent = OnboardingAgent(provider)

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
