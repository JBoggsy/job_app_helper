import logging

from flask import Blueprint, request

from backend.resume_parser import (
    allowed_file,
    parse_resume,
    save_resume,
    get_saved_resume,
    get_resume_text,
    delete_resume,
    get_parsed_resume,
    delete_parsed_resume,
    MAX_FILE_SIZE,
)

logger = logging.getLogger(__name__)

resume_bp = Blueprint("resume", __name__, url_prefix="/api/resume")


@resume_bp.route("", methods=["POST"])
def upload_resume():
    """Upload and parse a resume file (PDF or DOCX).

    Expects a multipart/form-data POST with a 'file' field.
    Saves the file and returns the parsed text content.
    """
    if "file" not in request.files:
        return {"error": "No file provided"}, 400

    file = request.files["file"]
    if not file.filename:
        return {"error": "No file selected"}, 400

    if not allowed_file(file.filename):
        return {"error": "Unsupported file type. Please upload a PDF or DOCX file."}, 400

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return {"error": f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB."}, 400

    try:
        # Parse first to validate the file content
        text = parse_resume(file_bytes, file.filename)

        # Save the file
        save_resume(file_bytes, file.filename)

        logger.info("Resume uploaded: %s (%d bytes, %d chars extracted)",
                     file.filename, len(file_bytes), len(text))

        return {
            "filename": file.filename,
            "size": len(file_bytes),
            "text": text,
            "text_length": len(text),
        }
    except ValueError as e:
        return {"error": str(e)}, 400
    except RuntimeError as e:
        logger.exception("Resume parsing failed")
        return {"error": str(e)}, 500


@resume_bp.route("", methods=["GET"])
def get_resume():
    """Get info about the currently saved resume, its parsed text, and structured data."""
    info = get_saved_resume()
    if not info:
        return {"resume": None}

    try:
        text = get_resume_text()
        parsed = get_parsed_resume()
        return {
            "resume": {
                "filename": info["filename"],
                "size": info["size"],
                "text": text,
                "text_length": len(text) if text else 0,
                "parsed": parsed,
            }
        }
    except Exception as e:
        logger.exception("Failed to read saved resume")
        return {
            "resume": {
                "filename": info["filename"],
                "size": info["size"],
                "text": None,
                "error": str(e),
            }
        }


@resume_bp.route("", methods=["DELETE"])
def remove_resume():
    """Delete the saved resume."""
    deleted = delete_resume()
    if deleted:
        return {"status": "deleted"}
    return {"status": "no_resume"}


@resume_bp.route("/parse", methods=["POST"])
def parse_resume_with_llm():
    """Parse the uploaded resume using an LLM to produce structured JSON.

    Uses the configured LLM provider to clean up raw extracted text and
    return a structured representation of the resume.
    """
    from backend.config_manager import get_llm_config
    from backend.llm.langchain_factory import create_langchain_model
    from backend.agent import ActiveResumeParser as ResumeParser

    # Get the raw resume text
    raw_text = get_resume_text()
    if not raw_text:
        return {"error": "No resume uploaded. Please upload a resume first."}, 400

    # Check LLM configuration
    llm_config = get_llm_config()
    if not llm_config["api_key"] and llm_config["provider"] != "ollama":
        return {"error": "LLM is not configured. Please configure your API key in Settings."}, 400

    try:
        model = create_langchain_model(
            llm_config["provider"],
            llm_config["api_key"],
            llm_config["model"],
        )
    except Exception as e:
        logger.error("Failed to create LLM model for resume parsing: %s", e)
        return {"error": f"Failed to initialize LLM provider: {str(e)}"}, 500

    try:
        parser = ResumeParser(model)
        parsed = parser.parse(raw_text)
        logger.info("Resume parsed successfully via LLM")
        return {"parsed": parsed}
    except RuntimeError as e:
        logger.exception("Resume parsing agent failed")
        return {"error": str(e)}, 500
    except Exception as e:
        logger.exception("Unexpected error during resume parsing")
        return {"error": f"Resume parsing failed: {str(e)}"}, 500
