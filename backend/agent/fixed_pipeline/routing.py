"""Routing Agent — classify user intent and extract structured parameters."""

import logging

from langchain_core.language_models import BaseChatModel
from pydantic import ValidationError

from .dspy_modules import RoutingModule
from .schemas import PARAM_SCHEMAS, RoutingResult

logger = logging.getLogger(__name__)

# Number of recent messages to include for context
HISTORY_WINDOW = 6

# Max retries when param validation fails
MAX_PARAM_RETRIES = 1


def route(model: BaseChatModel, messages: list[dict]) -> RoutingResult:
    """Classify the user's request and extract parameters.

    Args:
        model: LLM model instance.
        messages: Full conversation history (list of {role, content}).

    Returns:
        RoutingResult with request_type, params, entity_refs, acknowledgment.
        Falls back to general pipeline on any failure.
    """
    # Build the user message with recent history for context
    recent = messages[-HISTORY_WINDOW:] if len(messages) > HISTORY_WINDOW else messages
    user_msg = _format_history_for_routing(recent)

    logger.info("Routing — %d messages, last user msg: %s",
                len(messages), user_msg[-200:] if user_msg else "(empty)")

    try:
        result = _invoke_router(user_msg)

        # Validate params against the pipeline's schema; retry once on failure
        for attempt in range(MAX_PARAM_RETRIES + 1):
            schema = PARAM_SCHEMAS.get(result.request_type)
            if schema:
                try:
                    schema.model_validate(result.params)
                    break  # Valid — proceed
                except ValidationError as e:
                    if attempt < MAX_PARAM_RETRIES:
                        logger.warning(
                            "Param validation failed for %s (attempt %d): %s — retrying",
                            result.request_type, attempt + 1, e,
                        )
                        retry_msg = _format_validation_error(user_msg, result, e)
                        result = _invoke_router(retry_msg)
                    else:
                        logger.warning(
                            "Param validation failed for %s after retry: %s — falling back to general",
                            result.request_type, e,
                        )
                        break  # Fall through to return; agent.py handles ValidationError
            else:
                break  # No schema to validate against

        logger.info("Routed to '%s' — params=%s, ack=%s",
                    result.request_type, result.params, result.acknowledgment[:100])
        return result
    except Exception as e:
        logger.warning("Routing failed: %s — falling back to general", e, exc_info=True)

    # Fallback: general pipeline
    last_user_msg = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            last_user_msg = msg["content"]
            break

    return RoutingResult(
        request_type="general",
        params={"question": last_user_msg, "needs_profile": True},
        entity_refs=[],
        acknowledgment="",
    )


def _invoke_router(user_msg: str) -> RoutingResult:
    """Invoke the routing agent via DSPy module and return a validated RoutingResult."""
    module = RoutingModule()
    result = module(conversation_context=user_msg)
    if isinstance(result, RoutingResult):
        return result
    if isinstance(result, dict):
        return RoutingResult.model_validate(result)
    raise ValueError(f"Routing returned unexpected type: {type(result).__name__}")


def _format_validation_error(original_msg: str, result: RoutingResult, error: ValidationError) -> str:
    """Format a validation error as feedback for the routing agent retry."""
    return (
        f"{original_msg}\n\n"
        f"[SYSTEM: Your previous classification to '{result.request_type}' had "
        f"invalid params. Validation errors:\n{error}\n"
        f"Please fix the params and try again.]"
    )


def _format_history_for_routing(messages: list[dict]) -> str:
    """Format recent messages into a text block for the routing agent."""
    parts = []
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"]
        # Truncate very long messages for routing context
        if len(content) > 500:
            content = content[:500] + "..."
        parts.append(f"[{role}]: {content}")
    return "\n\n".join(parts)
