"""read_resume tool — read the user's uploaded resume."""

import logging

from ._registry import agent_tool

logger = logging.getLogger(__name__)


class ResumeMixin:
    @agent_tool(
        description="Read the user's uploaded resume.",
    )
    def read_resume(self):
        from backend.resume_parser import get_resume_text, get_parsed_resume, get_saved_resume

        info = get_saved_resume()
        if not info:
            return {"error": "No resume uploaded. The user hasn't uploaded a resume yet."}

        text = get_resume_text()
        parsed = get_parsed_resume()

        result = {"filename": info["filename"]}

        if parsed:
            result["parsed"] = parsed
        elif text:
            result["text"] = text
            result["text_length"] = len(text)

        logger.info("read_resume: filename=%s parsed=%s text_len=%s",
                     info["filename"], parsed is not None,
                     len(text) if text else 0)
        return result
