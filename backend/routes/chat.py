import json
import logging

from flask import Blueprint, Response, current_app, request, stream_with_context

from backend.agent.langchain_agent import LangChainAgent, LangChainOnboardingAgent
from backend.agent.user_profile import is_onboarding_in_progress, set_onboarding_in_progress
from backend.config_manager import get_llm_config, get_onboarding_llm_config, get_search_llm_config, get_integration_config
from backend.database import db
from backend.job_enrichment import enrich_job_data
from backend.llm.langchain_factory import create_langchain_model
from backend.models.chat import Conversation, Message
from backend.models.job import Job
from backend.models.search_result import SearchResult

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

    # Create LangChain model and agent
    try:
        model = create_langchain_model(
            llm_config["provider"],
            llm_config["api_key"],
            llm_config["model"],
        )
    except Exception as e:
        logger.error(f"Failed to create LLM model: {e}")
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
    # Create search sub-agent model (may be a cheaper model)
    search_llm_config = get_search_llm_config()
    search_model = None
    try:
        if search_llm_config["api_key"] or search_llm_config["provider"] == "ollama":
            search_model = create_langchain_model(
                search_llm_config["provider"],
                search_llm_config["api_key"],
                search_llm_config["model"],
            )
    except Exception as e:
        logger.warning("Failed to create search LLM model, falling back to main: %s", e)

    # Fall back to main model if search model not configured
    if search_model is None:
        search_model = model

    agent = LangChainAgent(
        model,
        search_api_key=integration_config["search_api_key"],
        adzuna_app_id=integration_config["adzuna_app_id"],
        adzuna_app_key=integration_config["adzuna_app_key"],
        adzuna_country=integration_config["adzuna_country"],
        jsearch_api_key=integration_config["jsearch_api_key"],
        conversation_id=convo_id,
        search_model=search_model,
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


@chat_bp.route("/conversations/<int:convo_id>/search-results", methods=["GET"])
def get_search_results(convo_id):
    convo = db.session.get(Conversation, convo_id)
    if not convo:
        return {"error": "Conversation not found"}, 404
    results = (
        SearchResult.query
        .filter_by(conversation_id=convo_id)
        .order_by(SearchResult.job_fit.desc(), SearchResult.created_at)
        .all()
    )
    return [r.to_dict() for r in results]


@chat_bp.route("/conversations/<int:convo_id>/search-results/<int:result_id>/add-to-tracker", methods=["POST"])
def add_search_result_to_tracker(convo_id, result_id):
    result = db.session.get(SearchResult, result_id)
    if not result or result.conversation_id != convo_id:
        return {"error": "Search result not found"}, 404
    if result.added_to_tracker:
        return {"error": "Already added to tracker", "job_id": result.tracker_job_id}, 409

    # Build initial job data from the search result
    job_data = {
        "company": result.company,
        "title": result.title,
        "url": result.url,
        "salary_min": result.salary_min,
        "salary_max": result.salary_max,
        "location": result.location,
        "remote_type": result.remote_type,
        "source": result.source,
        "requirements": result.requirements,
        "nice_to_haves": result.nice_to_haves,
    }

    # Enrich from URL if fields are missing
    enriched = _enrich_job_data_safe(job_data)

    job = Job(
        company=enriched.get("company", result.company),
        title=enriched.get("title", result.title),
        url=result.url,
        status="saved",
        salary_min=enriched.get("salary_min"),
        salary_max=enriched.get("salary_max"),
        location=enriched.get("location"),
        remote_type=enriched.get("remote_type"),
        source=enriched.get("source"),
        job_fit=result.job_fit,
        requirements=enriched.get("requirements"),
        nice_to_haves=enriched.get("nice_to_haves"),
        tags=enriched.get("tags"),
        notes=result.fit_reason,
    )
    db.session.add(job)
    db.session.flush()

    result.added_to_tracker = True
    result.tracker_job_id = job.id
    db.session.commit()

    enrichment_status = enriched.get("_enrichment_status", "skipped")
    fields_enriched = enriched.get("_fields_enriched", [])
    logger.info("add_to_tracker: job id=%d enrichment=%s fields=%s",
                job.id, enrichment_status, fields_enriched)

    return {
        "result": result.to_dict(),
        "job": job.to_dict(),
        "enrichment_status": enrichment_status,
        "fields_enriched": fields_enriched,
    }, 201


def _enrich_job_data_safe(job_data):
    """Attempt to enrich job data, falling back gracefully on any error.

    Uses the search LLM config (cheaper model) for enrichment.
    """
    try:
        # Get LLM model for enrichment (use search model — cheaper)
        search_config = get_search_llm_config()
        integration_config = get_integration_config()

        llm_model = None
        if search_config.get("api_key") or search_config.get("provider") == "ollama":
            llm_model = create_langchain_model(
                search_config["provider"],
                search_config.get("api_key", ""),
                search_config.get("model", ""),
            )

        return enrich_job_data(
            job_data=job_data,
            search_api_key=integration_config.get("search_api_key", ""),
            llm_model=llm_model,
        )
    except Exception as e:
        logger.warning("Job enrichment failed, using original data: %s", e)
        return job_data


def _get_onboarding_model():
    """Build the LangChain model for onboarding, falling back to the main config.

    Raises ValueError if LLM is not configured.
    """
    # Get config dynamically from config manager (not Flask's static config)
    onboarding_config = get_onboarding_llm_config()
    provider_name = onboarding_config["provider"]
    api_key = onboarding_config["api_key"]
    model = onboarding_config["model"]

    if not api_key and provider_name != "ollama":
        raise ValueError("LLM is not configured. Please configure your API key in Settings.")

    return create_langchain_model(provider_name, api_key, model)


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
        model = _get_onboarding_model()
        agent = LangChainOnboardingAgent(model)
    except Exception as e:
        logger.error(f"Failed to create onboarding model: {e}")
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
    # Use a different message when resuming a previously started onboarding.
    resuming = is_onboarding_in_progress()
    if resuming:
        kick_text = ("Hi! I started the onboarding interview before but didn't finish. "
                     "Please review my profile and continue from where we left off.")
    else:
        kick_text = "Hi! I'm new here."

    # Mark onboarding as in-progress (so resumption works if user leaves mid-interview)
    set_onboarding_in_progress()

    kick_msg = Message(conversation_id=convo_id, role="user", content=kick_text)
    db.session.add(kick_msg)
    db.session.commit()
    llm_messages = [{"role": "user", "content": kick_text}]

    try:
        model = _get_onboarding_model()
        agent = LangChainOnboardingAgent(model)
    except Exception as e:
        logger.error(f"Failed to create onboarding model: {e}")
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
